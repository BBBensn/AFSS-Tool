from pathlib import Path

from flask import Blueprint, Flask, flash, jsonify, redirect, render_template, request, url_for

from afss.sort_studio import bulk_update, clear_manual_override, get_profile_tree, save_title_overrides
from afss.tagging import search_json_entities


def build_sort_blueprint(db_path: Path | None = None, config_dir: Path | None = None) -> Blueprint:
    """Blueprint mit /<profile_id>/-Routen, damit ein Flask-Prozess mehrere Profile bedienen kann
    (gleiches Muster wie build_tag_blueprint)."""
    bp = Blueprint("sort", __name__, template_folder="templates")

    @bp.route("/<profile_id>/")
    def index(profile_id: str):
        artists = get_profile_tree(profile_id, db_path)
        return render_template("sort_index.html", profile_id=profile_id, artists=artists)

    @bp.route("/<profile_id>/search")
    def search(profile_id: str):
        kind = request.args.get("kind", "artist")
        query = request.args.get("q", "")
        matches = search_json_entities(kind, query, config_dir) if config_dir is not None else []
        return jsonify([{"id": eid, "name": name} for eid, name in matches])

    @bp.route("/<profile_id>/bulk", methods=["POST"])
    def bulk(profile_id: str):
        item_ids = [int(v) for v in request.form.getlist("item_id")]
        action = request.form.get("action", "")

        if not item_ids:
            flash("Bulk-Aktion: keine Dateien ausgewählt.", "error")
            return redirect(url_for("sort.index", profile_id=profile_id))

        if action == "set_artist":
            target_id = request.form.get("artist_target_id", "").strip()
            if not target_id:
                flash("Bitte zuerst einen Artist auswählen.", "error")
            else:
                n = bulk_update(item_ids, {"artist_id": target_id}, db_path, config_dir)
                flash(f"{n} Datei(en) neu zugeordnet.", "ok")
        elif action == "set_provider":
            target_id = request.form.get("provider_target_id", "").strip()
            if not target_id:
                flash("Bitte zuerst einen Provider auswählen.", "error")
            else:
                n = bulk_update(item_ids, {"provider_id": target_id}, db_path, config_dir)
                flash(f"{n} Datei(en) neu zugeordnet.", "ok")
        elif action == "set_collection":
            collection_name = request.form.get("collection_name", "").strip() or None
            n = bulk_update(item_ids, {"collection_name": collection_name}, db_path, config_dir)
            flash(f"{n} Datei(en) Collection gesetzt.", "ok")
        elif action == "clear_override":
            n = clear_manual_override(item_ids, db_path)
            flash(f"{n} Datei(en) auf automatische Zuordnung zurückgesetzt (nächster Resolve-Lauf greift wieder).", "ok")
        else:
            flash(f"Unbekannte Aktion: {action}", "error")

        return redirect(url_for("sort.index", profile_id=profile_id))

    @bp.route("/<profile_id>/titles", methods=["POST"])
    def titles(profile_id: str):
        values = {}
        prefix = "title_"
        for key, value in request.form.items():
            if key.startswith(prefix):
                try:
                    item_id = int(key[len(prefix):])
                except ValueError:
                    continue
                values[item_id] = value

        n = save_title_overrides(values, db_path)
        flash(f"{n} Titel gespeichert.", "ok")
        return redirect(url_for("sort.index", profile_id=profile_id))

    return bp


def create_app(profile_id: str, config_dir: Path, db_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = "afss-local-sort"  # nur 127.0.0.1
    app.register_blueprint(build_sort_blueprint(db_path, config_dir), url_prefix="/sort")

    @app.route("/")
    def _root():
        return redirect(url_for("sort.index", profile_id=profile_id))

    return app


def run_web(profile_id: str, config_dir: Path, port: int = 5153, db_path: Path | None = None) -> None:
    app = create_app(profile_id, config_dir, db_path)
    app.run(host="127.0.0.1", port=port, debug=False)
