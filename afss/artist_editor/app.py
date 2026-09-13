from pathlib import Path

from flask import Blueprint, Flask, flash, jsonify, redirect, render_template, request, url_for

from afss.artist_editor.import_parsers import parse_pasted_bio
from afss.artist_editor.store import (
    artist_from_form,
    bulk_set_field,
    delete_artist,
    distinct_field_values,
    load_artists,
    parse_partial_date,
    search_artists,
    slugify,
    sync_artist_to_db,
    tags_with_defaults,
    upsert_artist,
)
from afss.tagging import merge_entities

# Feste Allow-List statt beliebigem Feldpfad aus der Query - die Felder sind bewusst genau die, die
# als freies Textfeld ohne <datalist> im Formular stehen (echte Festwert-Felder wie gender_identity
# haben schon eine <datalist> und brauchen dieses Autocomplete nicht).
_AUTOCOMPLETE_FIELDS = {
    "nationality",
    "ethnicity",
    "birth_place.city",
    "birth_place.state",
    "birth_place.country_iso",
    "bra_size_eu",
    "artist_tags",
    "occupation",
    "pierce_locations",
}

# Felder, die über die Bulk-Bearbeitung in der Artist-Liste gesetzt werden können - bewusst eine
# eigene (größere) Allow-List als _AUTOCOMPLETE_FIELDS, da hier auch die <datalist>-Festwert-Felder
# aus dem Einzel-Formular sinnvoll sind (Bulk-Toolbar hat kein natives <datalist>, sondern nutzt für
# alle Felder dasselbe Fetch-Autocomplete). Reihenfolge bestimmt die Reihenfolge im Dropdown.
BULK_EDIT_FIELDS = [
    ("gender_identity", "Gender Identity"),
    ("sex_assigned_at_birth", "Sex Assigned at Birth"),
    ("sexual_orientation", "Sexual Orientation"),
    ("nationality", "Nationality"),
    ("ethnicity", "Ethnicity"),
    ("birth_place.city", "Geburtsort: Stadt"),
    ("birth_place.state", "Geburtsort: Bundesland"),
    ("birth_place.country_iso", "Geburtsort: Land (ISO)"),
    ("bra_size_eu", "Bra Size (EU)"),
    ("boobs_type", "Boobs Type"),
    ("body_type", "Body Type"),
    ("hair_color", "Hair Color"),
    ("eye_color", "Eye Color"),
    ("priority", "Priority"),
    ("occupation", "Occupation"),
    ("artist_tags", "Artist Tags"),
    ("pierce_locations", "Piercings"),
]
_BULK_EDIT_FIELD_LABELS = dict(BULK_EDIT_FIELDS)
_AUTOCOMPLETE_FIELDS |= _BULK_EDIT_FIELD_LABELS.keys()


def build_artist_editor_blueprint(config_dir: Path, db_path: Path | None = None) -> Blueprint:
    config_dir = Path(config_dir)
    artists_path = config_dir / "artists.json"
    bp = Blueprint("artist_editor", __name__, template_folder="templates")

    def _render_index():
        artists = sorted(load_artists(artists_path), key=lambda a: a.get("canonical_name", "").lower())
        return render_template("artist_list.html", artists=artists, bulk_fields=BULK_EDIT_FIELDS)

    @bp.route("/")
    def index():
        return _render_index()

    @bp.route("/bulk", methods=["POST"])
    def bulk():
        artist_ids = request.form.getlist("artist_id")
        field = request.form.get("field", "")
        value = request.form.get("value", "")

        if not artist_ids:
            flash("Bulk-Bearbeitung: keine Artists ausgewählt.", "error")
        elif field not in _BULK_EDIT_FIELD_LABELS:
            flash(f"Unbekanntes Feld: {field}", "error")
        else:
            n = bulk_set_field(artists_path, artist_ids, field, value)
            label = _BULK_EDIT_FIELD_LABELS[field]
            if value.strip():
                flash(f"{label} bei {n} Artist(s) auf '{value.strip()}' gesetzt.", "ok")
            else:
                flash(f"{label} bei {n} Artist(s) geleert.", "ok")

        return redirect(url_for("artist_editor.index"))

    @bp.route("/new")
    def new():
        # Die große Mehrheit der Einträge ist female (Identity & Sex Assigned at Birth) -
        # als Vorbelegung sparen, bleibt jederzeit überschreibbar/leerbar (z.B. für Duos).
        tags = tags_with_defaults({"gender_identity": "female", "sex_assigned_at_birth": "female"})
        return render_template(
            "artist_form.html",
            artist=None,
            tags=tags,
            birth=parse_partial_date(""),
            original_id="",
        )

    @bp.route("/edit/<artist_id>")
    def edit(artist_id: str):
        artists = load_artists(artists_path)
        artist = next((a for a in artists if a.get("id") == artist_id), None)
        if artist is None:
            flash(f"Artist '{artist_id}' nicht gefunden.", "error")
            return redirect(url_for("artist_editor.index"))
        tags = tags_with_defaults(artist.get("default_tags", {}))
        return render_template(
            "artist_form.html",
            artist=artist,
            tags=tags,
            birth=parse_partial_date(tags.get("birth_date", "")),
            original_id=artist_id,
        )

    @bp.route("/save", methods=["POST"])
    def save():
        entry = artist_from_form(request.form)
        original_id = request.form.get("original_id", "").strip() or None

        if not entry["canonical_name"]:
            flash("Canonical Name darf nicht leer sein.", "error")
            if original_id:
                return redirect(url_for("artist_editor.edit", artist_id=original_id))
            return redirect(url_for("artist_editor.new"))

        if not entry["id"]:
            entry["id"] = "artist_" + (slugify(entry["canonical_name"]) or "unbenannt")

        upsert_artist(artists_path, entry, original_id)
        sync_artist_to_db(entry, original_id, db_path)
        flash(f"'{entry['canonical_name']}' gespeichert.", "ok")
        return redirect(url_for("artist_editor.index"))

    @bp.route("/parse-bio", methods=["POST"])
    def parse_bio():
        """Parst manuell eingefügten Bio-Text lokal - kein Netzwerkzugriff. Der Nutzer
        kopiert den Text selbst aus seinem eigenen Browser."""
        source = request.form.get("source", "")
        text = request.form.get("text", "")
        return jsonify(parse_pasted_bio(source, text))

    @bp.route("/search")
    def search():
        query = request.args.get("q", "")
        exclude_id = request.args.get("exclude", "")
        return jsonify(search_artists(artists_path, query, exclude_id))

    @bp.route("/field-values")
    def field_values():
        field = request.args.get("field", "")
        if field not in _AUTOCOMPLETE_FIELDS:
            return jsonify([])
        query = request.args.get("q", "")
        return jsonify(distinct_field_values(artists_path, field, query))

    @bp.route("/merge/<source_id>", methods=["POST"])
    def merge(source_id: str):
        target_id = request.form.get("target_id", "").strip()
        if not target_id:
            flash("Merge: bitte einen Ziel-Artist auswählen.", "error")
            return redirect(url_for("artist_editor.edit", artist_id=source_id))

        try:
            result = merge_entities("artist", source_id, target_id, config_dir, db_path)
        except ValueError as exc:
            flash(f"Merge fehlgeschlagen: {exc}", "error")
            return redirect(url_for("artist_editor.edit", artist_id=source_id))

        artists = load_artists(artists_path)
        target_name = next((a["canonical_name"] for a in artists if a["id"] == target_id), target_id)
        msg = f"'{source_id}' in '{target_name}' gemerged ({result['moved_items']} Dateien umgehängt)."
        if result["conflict"]:
            msg += f" Achtung: Alias-Konflikt mit '{result['conflict']['conflict_with']}' nicht übernommen."
        flash(msg, "ok")
        return redirect(url_for("artist_editor.edit", artist_id=target_id))

    @bp.route("/delete/<artist_id>", methods=["POST"])
    def delete(artist_id: str):
        artists = load_artists(artists_path)
        artist = next((a for a in artists if a.get("id") == artist_id), None)
        name = artist["canonical_name"] if artist else artist_id

        if delete_artist(artists_path, artist_id):
            flash(f"'{name}' gelöscht.", "ok")
        else:
            flash(f"Artist '{artist_id}' nicht gefunden.", "error")

        return redirect(url_for("artist_editor.index"))

    @bp.errorhandler(Exception)
    def _handle_any_error(exc: Exception):
        # Sicherheitsnetz analog zum Sortier-Studio (siehe sort_web/app.py) - ohne das würde ein
        # unerwarteter Fehler in der Bulk-Route nur als nackter 500 statt als brauchbare Meldung landen.
        flash(f"Unerwarteter Fehler: {exc}", "error")
        return redirect(url_for("artist_editor.index"))

    return bp


def create_app(config_dir: Path, db_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = "afss-local-artist-editor"  # nur 127.0.0.1
    app.register_blueprint(build_artist_editor_blueprint(config_dir, db_path), url_prefix="/artists")

    @app.route("/")
    def _root():
        return redirect(url_for("artist_editor.index"))

    return app


def run_web(config_dir: Path, port: int = 5152, db_path: Path | None = None) -> None:
    app = create_app(config_dir, db_path)
    app.run(host="127.0.0.1", port=port, debug=False)
