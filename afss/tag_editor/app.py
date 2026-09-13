from pathlib import Path

from flask import Blueprint, Flask, flash, jsonify, redirect, render_template, request, url_for

from afss.sort_studio import list_all_tags, rename_tag, search_tags


def build_tag_editor_blueprint(db_path: Path | None = None) -> Blueprint:
    """Blueprint mit Übersicht über alle im Sortier-Studio vergebenen Tags. Anders als
    Artist/Provider/Studio gibt es für Tags keine eigene Tabelle und kein JSON-Config-Store - die
    Übersicht liest direkt aus media_items.tags (siehe sort_studio.py::list_all_tags), daher
    braucht dieser Blueprint (im Unterschied zu artist_editor/sort_web) keinen config_dir."""
    bp = Blueprint("tag_editor", __name__, template_folder="templates")

    @bp.route("/")
    def index():
        tags = list_all_tags(db_path)
        return render_template("tag_index.html", tags=tags, total_tags=len(tags))

    @bp.route("/search")
    def search():
        query = request.args.get("q", "")
        return jsonify(search_tags(query, db_path))

    @bp.route("/rename", methods=["POST"])
    def rename():
        old_tag = request.form.get("old_tag", "").strip()
        new_tag = request.form.get("new_tag", "").strip()
        if not old_tag:
            flash("Bitte einen vorhandenen Tag auswählen.", "error")
        else:
            try:
                n = rename_tag(old_tag, new_tag, db_path)
                if new_tag:
                    flash(f"Tag '{old_tag}' bei {n} Datei(en) zu '{new_tag}' geändert.", "ok")
                else:
                    flash(f"Tag '{old_tag}' bei {n} Datei(en) entfernt.", "ok")
            except Exception as exc:
                flash(f"Fehler beim Umbenennen: {exc}", "error")
        return redirect(url_for("tag_editor.index"))

    return bp


def create_app(db_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = "afss-local-tag-editor"  # nur 127.0.0.1
    app.register_blueprint(build_tag_editor_blueprint(db_path), url_prefix="/tags")

    @app.route("/")
    def _root():
        return redirect(url_for("tag_editor.index"))

    return app


def run_web(port: int = 5154, db_path: Path | None = None) -> None:
    app = create_app(db_path)
    app.run(host="127.0.0.1", port=port, debug=False)
