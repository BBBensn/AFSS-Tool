from pathlib import Path

from flask import Blueprint, Flask, jsonify, redirect, render_template, request, url_for

from afss.suggest import suggest_action
from afss.tagging import (
    assign_to_existing_entity,
    assign_to_new_entity,
    get_pending_unresolved,
    ignore_folder,
    set_category,
    set_trash,
    search_entities,
)

_KIND_BY_ACTION = {
    "new_artist": "artist",
    "existing_artist": "artist",
    "new_provider": "provider",
    "existing_provider": "provider",
}


def build_tag_blueprint(db_path: Path | None = None) -> Blueprint:
    """Blueprint mit /<profile_id>/-Routen, damit ein Flask-Prozess mehrere Profile bedienen kann
    (Standalone `afss tag --web` UND das Dashboard nutzen denselben Blueprint)."""
    bp = Blueprint("tag", __name__, template_folder="templates")

    @bp.route("/<profile_id>/")
    def index(profile_id: str):
        rows = get_pending_unresolved(profile_id, db_path)
        rows_with_suggestion = [(row, suggest_action(row[1])) for row in rows]
        suggested_count = sum(1 for _row, suggestion in rows_with_suggestion if suggestion)
        return render_template(
            "index.html", profile_id=profile_id, rows=rows_with_suggestion, suggested_count=suggested_count
        )

    @bp.route("/<profile_id>/search")
    def search(profile_id: str):
        kind = request.args.get("kind", "artist")
        query = request.args.get("q", "")
        matches = search_entities(kind, query, db_path)
        return jsonify([{"id": eid, "name": name} for eid, name in matches])

    @bp.route("/<profile_id>/assign/<int:unresolved_id>", methods=["POST"])
    def assign(profile_id: str, unresolved_id: int):
        action = request.form.get("action", "")

        if action == "ignore":
            ignore_folder(unresolved_id, db_path)
        elif action == "category":
            set_category(unresolved_id, db_path)
        elif action == "trash":
            set_trash(unresolved_id, db_path)
        elif action in ("new_artist", "new_provider"):
            name = request.form.get("canonical_name", "").strip()
            if name:
                assign_to_new_entity(unresolved_id, _KIND_BY_ACTION[action], name, db_path)
        elif action in ("existing_artist", "existing_provider"):
            entity_id = request.form.get("entity_id", "").strip()
            if entity_id:
                assign_to_existing_entity(unresolved_id, _KIND_BY_ACTION[action], entity_id, db_path)

        return redirect(url_for("tag.index", profile_id=profile_id))

    @bp.route("/<profile_id>/accept_suggestions", methods=["POST"])
    def accept_suggestions(profile_id: str):
        """Übernimmt NUR die per Muster erkannten Vorschläge (category/trash), nichts Identitätsbezogenes."""
        rows = get_pending_unresolved(profile_id, db_path)
        for unresolved_id, folder_name, _level, _count, _sample in rows:
            suggestion = suggest_action(folder_name)
            if suggestion == "trash":
                set_trash(unresolved_id, db_path)
            elif suggestion == "category":
                set_category(unresolved_id, db_path)

        return redirect(url_for("tag.index", profile_id=profile_id))

    return bp


def create_app(profile_id: str, db_path: Path | None = None) -> Flask:
    app = Flask(__name__)
    app.register_blueprint(build_tag_blueprint(db_path), url_prefix="/tag")

    @app.route("/")
    def _root():
        return redirect(url_for("tag.index", profile_id=profile_id))

    return app


def run_web(profile_id: str, db_path: Path | None = None, port: int = 5151) -> None:
    app = create_app(profile_id, db_path)
    app.run(host="127.0.0.1", port=port, debug=False)
