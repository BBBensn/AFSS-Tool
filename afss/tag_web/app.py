from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

from afss.tagging import (
    assign_to_existing_entity,
    assign_to_new_entity,
    get_pending_unresolved,
    ignore_folder,
    search_entities,
)

_KIND_BY_ACTION = {
    "new_artist": "artist",
    "existing_artist": "artist",
    "new_provider": "provider",
    "existing_provider": "provider",
}


def create_app(profile_id: str, db_path: Path | None = None) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        rows = get_pending_unresolved(profile_id, db_path)
        return render_template("index.html", profile_id=profile_id, rows=rows)

    @app.route("/search")
    def search():
        kind = request.args.get("kind", "artist")
        query = request.args.get("q", "")
        matches = search_entities(kind, query, db_path)
        return jsonify([{"id": eid, "name": name} for eid, name in matches])

    @app.route("/assign/<int:unresolved_id>", methods=["POST"])
    def assign(unresolved_id: int):
        action = request.form.get("action", "")

        if action == "ignore":
            ignore_folder(unresolved_id, db_path)
        elif action in ("new_artist", "new_provider"):
            name = request.form.get("canonical_name", "").strip()
            if name:
                assign_to_new_entity(unresolved_id, _KIND_BY_ACTION[action], name, db_path)
        elif action in ("existing_artist", "existing_provider"):
            entity_id = request.form.get("entity_id", "").strip()
            if entity_id:
                assign_to_existing_entity(unresolved_id, _KIND_BY_ACTION[action], entity_id, db_path)

        return redirect(url_for("index"))

    return app


def run_web(profile_id: str, db_path: Path | None = None, port: int = 5151) -> None:
    app = create_app(profile_id, db_path)
    app.run(host="127.0.0.1", port=port, debug=False)
