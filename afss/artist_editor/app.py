from pathlib import Path

from flask import Blueprint, Flask, flash, redirect, render_template, request, url_for

from afss.artist_editor.store import (
    artist_from_form,
    delete_artist,
    load_artists,
    parse_partial_date,
    slugify,
    tags_with_defaults,
    upsert_artist,
)


def build_artist_editor_blueprint(config_dir: Path) -> Blueprint:
    artists_path = Path(config_dir) / "artists.json"
    bp = Blueprint("artist_editor", __name__, template_folder="templates")

    @bp.route("/")
    def index():
        artists = sorted(load_artists(artists_path), key=lambda a: a.get("canonical_name", "").lower())
        return render_template("artist_list.html", artists=artists)

    @bp.route("/new")
    def new():
        return render_template(
            "artist_form.html",
            artist=None,
            tags=tags_with_defaults({}),
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
        flash(f"'{entry['canonical_name']}' gespeichert.", "ok")
        return redirect(url_for("artist_editor.index"))

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

    return bp


def create_app(config_dir: Path) -> Flask:
    app = Flask(__name__)
    app.secret_key = "afss-local-artist-editor"  # nur 127.0.0.1
    app.register_blueprint(build_artist_editor_blueprint(config_dir), url_prefix="/artists")

    @app.route("/")
    def _root():
        return redirect(url_for("artist_editor.index"))

    return app


def run_web(config_dir: Path, port: int = 5152) -> None:
    app = create_app(config_dir)
    app.run(host="127.0.0.1", port=port, debug=False)
