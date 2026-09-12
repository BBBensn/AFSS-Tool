from pathlib import Path

from flask import Blueprint, Flask, flash, jsonify, redirect, render_template, request, url_for

from afss.sort_studio import (
    add_co_artist,
    add_tags,
    bulk_update,
    clear_manual_override,
    create_entity,
    dissolve_collection,
    get_locked_artist_keys,
    get_profile_tree,
    remove_co_artist,
    rename_tag,
    save_tags,
    save_title_overrides,
    search_tags,
    set_artist_locked,
    set_item_status,
)
from afss.tagging import search_json_entities

_SORT_OPTIONS = ("collection", "filename", "ext", "folder")


def build_sort_blueprint(db_path: Path | None = None, config_dir: Path | None = None) -> Blueprint:
    """Blueprint mit /<profile_id>/-Routen, damit ein Flask-Prozess mehrere Profile bedienen kann
    (gleiches Muster wie build_tag_blueprint).

    Bulk-Aktionen (bulk/details) rendern die Seite direkt in derselben Response statt per
    redirect+neuem GET - das JS im Template holt diese Response per fetch() und tauscht nur den
    Inhalt von #app-root aus, ohne echte Seitennavigation. Dadurch bleiben Scroll-Position,
    Browser-History usw. unangetastet; ein Redirect würde das wieder zunichtemachen."""
    bp = Blueprint("sort", __name__, template_folder="templates")

    def _sort_by() -> str:
        sort_by = request.values.get("sort", "collection")
        return sort_by if sort_by in _SORT_OPTIONS else "collection"

    def _render_page(profile_id: str):
        sort_by = _sort_by()
        artists = get_profile_tree(profile_id, db_path, sort_by)
        locked_artist_keys = get_locked_artist_keys(db_path)
        all_files = [item for a in artists.values() for c in a["collections"].values() for item in c["files"]]
        present_profiles = sorted({item["profile_id"] for item in all_files})
        # Bei vielen Dateien machen von Anfang an aufgeklappte <details> die Seite spürbar
        # langsam (jede sichtbare Zeile kostet Layout/Paint) - ab einer gewissen Größe daher
        # eingeklappt starten, der Nutzer klappt gezielt auf was er braucht.
        default_open = len(all_files) <= 150
        return render_template(
            "sort_index.html",
            profile_id=profile_id,
            artists=artists,
            present_profiles=present_profiles,
            default_open=default_open,
            total_files=len(all_files),
            sort_by=sort_by,
            locked_artist_keys=locked_artist_keys,
        )

    @bp.route("/<profile_id>/")
    def index(profile_id: str):
        return _render_page(profile_id)

    @bp.route("/<profile_id>/search")
    def search(profile_id: str):
        kind = request.args.get("kind", "artist")
        query = request.args.get("q", "")
        try:
            if kind == "tag":
                # Tags haben keine eigene ID (reiner Freitext) - id=name, das JS braucht nur den Text.
                matches = [(t, t) for t in search_tags(query, db_path)]
            else:
                matches = search_json_entities(kind, query, config_dir) if config_dir is not None else []
        except Exception:
            # Antwortet bewusst leer statt mit der HTML-Fehlerseite des allgemeinen Error-Handlers -
            # das JS hier erwartet JSON (r.json()), eine HTML-Antwort würde nur einen zusätzlichen,
            # schwerer nachvollziehbaren Fehler beim Parsen erzeugen.
            return jsonify([])
        return jsonify([{"id": eid, "name": name} for eid, name in matches])

    def _resolve_artist_or_provider(kind: str, target_id: str, new_name: str) -> str | None:
        """target_id gewinnt (bestehender Treffer aus der Suche); sonst wird bei vorhandenem
        new_name ein neuer Eintrag angelegt. Gibt None zurück wenn beides leer ist (Feld einfach
        nicht ausgefüllt - beim kombinierten 'Alles setzen' kein Fehler, sondern übersprungen)."""
        if target_id:
            return target_id
        if new_name and config_dir is not None:
            return create_entity(kind, new_name, config_dir, db_path)
        return None

    @bp.route("/<profile_id>/bulk", methods=["POST"])
    def bulk(profile_id: str):
        item_ids = [int(v) for v in request.form.getlist("item_id")]
        action = request.form.get("action", "")

        if not item_ids:
            flash("Bulk-Aktion: keine Dateien ausgewählt.", "error")
            return _render_page(profile_id)

        try:
            _dispatch_bulk_action(action, item_ids)
        except Exception as exc:  # Fehler sichtbar machen statt generischem 500 (siehe dashboard/app.py::run_action) -
            # ohne das hier landete jeder Fehler als nichtssagendes "Aktion fehlgeschlagen" beim Nutzer.
            flash(f"Fehler bei Aktion '{action}': {exc}", "error")

        return _render_page(profile_id)

    def _dispatch_bulk_action(action: str, item_ids: list[int]) -> None:
        if action == "set_artist":
            target_id = request.form.get("artist_target_id", "").strip()
            if not target_id:
                flash("Bitte zuerst einen Artist auswählen.", "error")
            else:
                n = bulk_update(item_ids, {"artist_id": target_id}, db_path, config_dir)
                flash(f"{n} Datei(en) neu zugeordnet.", "ok")
        elif action == "create_and_set_artist":
            name = request.form.get("artist_search_text", "").strip()
            if not name:
                flash("Bitte einen Namen für den neuen Artist eingeben.", "error")
            elif config_dir is None:
                flash("Kein Config-Verzeichnis konfiguriert.", "error")
            else:
                entity_id = create_entity("artist", name, config_dir, db_path)
                n = bulk_update(item_ids, {"artist_id": entity_id}, db_path, config_dir)
                flash(f"Neuer Artist '{name}' angelegt und {n} Datei(en) zugeordnet.", "ok")
        elif action == "set_provider":
            target_id = request.form.get("provider_target_id", "").strip()
            if not target_id:
                flash("Bitte zuerst einen Provider auswählen.", "error")
            else:
                n = bulk_update(item_ids, {"provider_id": target_id}, db_path, config_dir)
                flash(f"{n} Datei(en) neu zugeordnet.", "ok")
        elif action == "create_and_set_provider":
            name = request.form.get("provider_search_text", "").strip()
            if not name:
                flash("Bitte einen Namen für den neuen Provider eingeben.", "error")
            elif config_dir is None:
                flash("Kein Config-Verzeichnis konfiguriert.", "error")
            else:
                entity_id = create_entity("provider", name, config_dir, db_path)
                n = bulk_update(item_ids, {"provider_id": entity_id}, db_path, config_dir)
                flash(f"Neuer Provider '{name}' angelegt und {n} Datei(en) zugeordnet.", "ok")
        elif action == "set_studio":
            target_id = request.form.get("studio_target_id", "").strip()
            if not target_id:
                flash("Bitte zuerst ein Studio auswählen.", "error")
            else:
                n = bulk_update(item_ids, {"studio_id": target_id}, db_path, config_dir)
                flash(f"{n} Datei(en) neu zugeordnet.", "ok")
        elif action == "create_and_set_studio":
            name = request.form.get("studio_search_text", "").strip()
            if not name:
                flash("Bitte einen Namen für das neue Studio eingeben.", "error")
            elif config_dir is None:
                flash("Kein Config-Verzeichnis konfiguriert.", "error")
            else:
                entity_id = create_entity("studio", name, config_dir, db_path)
                n = bulk_update(item_ids, {"studio_id": entity_id}, db_path, config_dir)
                flash(f"Neues Studio '{name}' angelegt und {n} Datei(en) zugeordnet.", "ok")
        elif action == "set_collection":
            collection_name = request.form.get("collection_name", "").strip() or None
            n = bulk_update(item_ids, {"collection_name": collection_name}, db_path, config_dir)
            flash(f"{n} Datei(en) Collection gesetzt.", "ok")
        elif action == "clear_artist":
            n = bulk_update(item_ids, {"artist_id": None}, db_path, config_dir)
            flash(f"{n} Datei(en): Artist entfernt.", "ok")
        elif action == "clear_provider":
            n = bulk_update(item_ids, {"provider_id": None}, db_path, config_dir)
            flash(f"{n} Datei(en): Provider entfernt.", "ok")
        elif action == "clear_studio":
            n = bulk_update(item_ids, {"studio_id": None}, db_path, config_dir)
            flash(f"{n} Datei(en): Studio entfernt.", "ok")
        elif action == "dissolve_collection":
            collection_name = request.form.get("dissolve_collection_name", "")
            n = dissolve_collection(item_ids, collection_name, db_path)
            flash(f"{n} Datei(en): Collection aufgelöst, als Tag übernommen.", "ok")
        elif action == "clear_override":
            n = clear_manual_override(item_ids, db_path)
            flash(f"{n} Datei(en) auf automatische Zuordnung zurückgesetzt (nächster Resolve-Lauf greift wieder).", "ok")
        elif action == "set_status":
            status = request.form.get("item_status", "").strip()
            n = set_item_status(item_ids, status, db_path)
            if n:
                flash(f"{n} Datei(en) auf Status '{status}' gesetzt.", "ok")
            else:
                flash("Unbekannter Status.", "error")
        elif action == "add_co_artist":
            target_id = request.form.get("co_artist_target_id", "").strip()
            if not target_id:
                flash("Bitte zuerst einen Co-Artist auswählen.", "error")
            else:
                n = add_co_artist(item_ids, target_id, db_path, config_dir)
                flash(f"Co-Artist bei {n} Datei(en) ergänzt.", "ok")
        elif action == "create_and_add_co_artist":
            name = request.form.get("co_artist_search_text", "").strip()
            if not name:
                flash("Bitte einen Namen für den neuen Co-Artist eingeben.", "error")
            elif config_dir is None:
                flash("Kein Config-Verzeichnis konfiguriert.", "error")
            else:
                entity_id = create_entity("artist", name, config_dir, db_path)
                n = add_co_artist(item_ids, entity_id, db_path, config_dir)
                flash(f"Neuer Artist '{name}' angelegt und als Co-Artist bei {n} Datei(en) ergänzt.", "ok")
        elif action == "add_tags":
            new_tags = [t for t in request.form.get("new_tags", "").split(",")]
            n = add_tags(item_ids, new_tags, db_path)
            flash(f"Tags bei {n} Datei(en) ergänzt.", "ok")
        elif action == "apply_all":
            applied = []

            artist_id = _resolve_artist_or_provider(
                "artist", request.form.get("artist_target_id", "").strip(), request.form.get("artist_search_text", "").strip()
            )
            if artist_id:
                bulk_update(item_ids, {"artist_id": artist_id}, db_path, config_dir)
                applied.append("Artist")

            provider_id = _resolve_artist_or_provider(
                "provider", request.form.get("provider_target_id", "").strip(), request.form.get("provider_search_text", "").strip()
            )
            if provider_id:
                bulk_update(item_ids, {"provider_id": provider_id}, db_path, config_dir)
                applied.append("Provider")

            studio_id = _resolve_artist_or_provider(
                "studio", request.form.get("studio_target_id", "").strip(), request.form.get("studio_search_text", "").strip()
            )
            if studio_id:
                bulk_update(item_ids, {"studio_id": studio_id}, db_path, config_dir)
                applied.append("Studio")

            collection_name = request.form.get("collection_name", "").strip()
            if collection_name:
                bulk_update(item_ids, {"collection_name": collection_name}, db_path, config_dir)
                applied.append("Collection")

            status = request.form.get("item_status", "").strip()
            if status in ("active", "trash", "extra"):
                set_item_status(item_ids, status, db_path)
                applied.append("Status")

            co_artist_id = _resolve_artist_or_provider(
                "artist", request.form.get("co_artist_target_id", "").strip(), request.form.get("co_artist_search_text", "").strip()
            )
            if co_artist_id:
                add_co_artist(item_ids, co_artist_id, db_path, config_dir)
                applied.append("Co-Artist")

            new_tags_raw = request.form.get("new_tags", "").strip()
            if new_tags_raw:
                add_tags(item_ids, new_tags_raw.split(","), db_path)
                applied.append("Tags")

            if applied:
                flash(f"{len(item_ids)} Datei(en): {', '.join(applied)} gesetzt.", "ok")
            else:
                flash("Kein Feld ausgefüllt - nichts geändert.", "error")
        else:
            flash(f"Unbekannte Aktion: {action}", "error")

    @bp.route("/<profile_id>/details", methods=["POST"])
    def details(profile_id: str):
        titles = {}
        tags = {}
        for key, value in request.form.items():
            if key.startswith("title_"):
                try:
                    titles[int(key[len("title_"):])] = value
                except ValueError:
                    continue
            elif key.startswith("tags_"):
                try:
                    tags[int(key[len("tags_"):])] = value
                except ValueError:
                    continue

        try:
            n_titles, n_titles_changed = save_title_overrides(titles, db_path)
            n_tags, n_tags_changed = save_tags(tags, db_path)
            # Das Formular schickt IMMER alle sichtbaren Zeilen mit (nicht nur die geänderten) -
            # ohne die separate "davon geändert"-Zahl wäre kaum nachvollziehbar, ob man aus Versehen
            # eine falsche Zeile mitbearbeitet hat.
            flash(
                f"{n_titles} Titel-Felder geprüft ({n_titles_changed} geändert), "
                f"{n_tags} Tag-Felder geprüft ({n_tags_changed} geändert).",
                "ok",
            )
        except Exception as exc:
            flash(f"Fehler beim Speichern: {exc}", "error")
        return _render_page(profile_id)

    @bp.route("/<profile_id>/remove-co-artist/<int:item_id>/<artist_id>", methods=["POST"])
    def remove_co_artist_route(profile_id: str, item_id: int, artist_id: str):
        try:
            remove_co_artist(item_id, artist_id, db_path)
        except Exception as exc:
            flash(f"Fehler beim Entfernen: {exc}", "error")
        return _render_page(profile_id)

    @bp.route("/<profile_id>/toggle-lock/<artist_key>", methods=["POST"])
    def toggle_lock(profile_id: str, artist_key: str):
        locked = request.args.get("locked", "1") == "1"
        try:
            set_artist_locked(artist_key, locked, db_path)
        except Exception as exc:
            flash(f"Fehler beim Sperren/Entsperren: {exc}", "error")
        return _render_page(profile_id)

    @bp.route("/<profile_id>/rename-tag", methods=["POST"])
    def rename_tag_route(profile_id: str):
        old_tag = request.form.get("old_tag", "").strip()
        new_tag = request.form.get("new_tag", "").strip()
        if not old_tag:
            flash("Bitte zuerst einen vorhandenen Tag auswählen.", "error")
        else:
            try:
                n = rename_tag(old_tag, new_tag, db_path)
                if new_tag:
                    flash(f"Tag '{old_tag}' bei {n} Datei(en) profilübergreifend zu '{new_tag}' geändert.", "ok")
                else:
                    flash(f"Tag '{old_tag}' bei {n} Datei(en) profilübergreifend entfernt.", "ok")
            except Exception as exc:
                flash(f"Fehler beim Umbenennen: {exc}", "error")
        return _render_page(profile_id)

    @bp.errorhandler(Exception)
    def _handle_any_error(exc: Exception):
        # Sicherheitsnetz zusätzlich zu den try/excepts in den einzelnen Routen: falls ein Fehler
        # aus _render_page() selbst kommt (z.B. beim Rendern nach einer erfolgreichen Aktion), gäbe
        # es sonst trotz der try/excepts oben noch einen nackten 500 - der Nutzer sähe wieder nur
        # das nichtssagende "Aktion fehlgeschlagen" statt der echten Ursache.
        profile_id = (request.view_args or {}).get("profile_id", "all")
        flash(f"Unerwarteter Fehler: {exc}", "error")
        try:
            return _render_page(profile_id)
        except Exception:
            return f"Unerwarteter Fehler, Seite konnte nicht neu geladen werden: {exc}", 200

    return bp


def create_app(profile_id: str, config_dir: Path, db_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = "afss-local-sort"  # nur 127.0.0.1
    # Siehe ausfuehrlicher Kommentar in afss/dashboard/app.py::create_app - beide Limits betreffen
    # grosse Formular-Uploads (viele item_id-Checkboxen) und sind fuer dieses rein lokale
    # Single-User-Tool unkritisch. MAX_FORM_PARTS ist besonders wichtig: Werkzeug faellt beim
    # Ueberschreiten *stillschweigend* auf ein leeres Formular zurueck statt einen Fehler zu werfen.
    app.config["MAX_FORM_MEMORY_SIZE"] = None
    app.config["MAX_FORM_PARTS"] = None
    app.register_blueprint(build_sort_blueprint(db_path, config_dir), url_prefix="/sort")

    @app.route("/")
    def _root():
        return redirect(url_for("sort.index", profile_id=profile_id))

    return app


def run_web(profile_id: str, config_dir: Path, port: int = 5153, db_path: Path | None = None) -> None:
    app = create_app(profile_id, config_dir, db_path)
    # threaded=True: siehe Kommentar in afss/dashboard/app.py::run_dashboard - grosse Bulk-Aktionen
    # duerfen den einzigen Worker-Thread nicht komplett blockieren.
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
