from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

from afss.apply import apply_profile
from afss.config import load_profiles
from afss.dedupe import apply_dedupe, dedupe_profile
from afss.naming import plan_profile, write_plan_report
from afss.report import report_overview
from afss.resolve import resolve_profile
from afss.scan import scan_profile
from afss.tag_web.app import build_tag_blueprint


def create_app(config_dir: Path, db_path: Path | None = None) -> Flask:
    config_dir = Path(config_dir)
    app = Flask(__name__)
    app.secret_key = "afss-local-dashboard"  # nur 127.0.0.1, kein Security-relevanter Wert
    app.register_blueprint(build_tag_blueprint(db_path), url_prefix="/tag")

    @app.route("/")
    def index():
        try:
            profiles = load_profiles(config_dir)
        except (FileNotFoundError, ValueError) as exc:
            return render_template("dashboard.html", rows=[], config_dir=str(config_dir), config_error=str(exc))

        stats_by_profile = {r["profile_id"]: r for r in report_overview(db_path=db_path)}
        rows = [{"profile": p, "stats": stats_by_profile.get(p["id"])} for p in profiles]
        return render_template("dashboard.html", rows=rows, config_dir=str(config_dir), config_error=None)

    @app.route("/run/<action>/<profile_id>", methods=["POST"])
    def run_action(action: str, profile_id: str):
        try:
            if action == "scan":
                result = scan_profile(profile_id, config_dir, db_path)
                flash(f"Scan '{profile_id}': {result['total_files']} Dateien gefunden.", "ok")
            elif action == "resolve":
                result = resolve_profile(profile_id, db_path)
                flash(f"Resolve '{profile_id}': {result['resolved']}/{result['total']} resolved.", "ok")
            elif action == "dedupe":
                result = dedupe_profile(profile_id, db_path)
                flash(
                    f"Dedupe '{profile_id}': {result['groups']} Gruppen, "
                    f"{result['duplicate_files']} Duplikate markiert.",
                    "ok",
                )
            elif action == "dedupe_apply":
                result = apply_dedupe(profile_id, db_path)
                flash(f"Dedupe-Apply '{profile_id}': {result['deleted']} Dateien gelöscht.", "ok")
            elif action == "plan":
                result = plan_profile(profile_id, config_dir, db_path)
                write_plan_report(result, Path(f"plan_{profile_id}.csv"))
                flash(
                    f"Plan '{profile_id}': {len(result['ready'])} ready, "
                    f"{len(result['needs_review'])} needs_review (plan_{profile_id}.csv geschrieben).",
                    "ok",
                )
            elif action == "apply":
                target = request.form.get("target", "").strip()
                if not target:
                    flash("Apply: Zielverzeichnis fehlt.", "error")
                else:
                    result = apply_profile(profile_id, Path(target), db_path)
                    flash(
                        f"Apply '{profile_id}': {result['copied']} kopiert, "
                        f"{result['verified']} verifiziert, {len(result['failed'])} fehlgeschlagen.",
                        "ok",
                    )
            else:
                flash(f"Unbekannte Aktion: {action}", "error")
        except Exception as exc:  # Fehler im Dashboard sichtbar machen statt 500-Seite
            flash(f"Fehler bei '{action}' für '{profile_id}': {exc}", "error")

        return redirect(url_for("index"))

    return app


def run_dashboard(config_dir: Path, db_path: Path | None = None, port: int = 5150) -> None:
    app = create_app(config_dir, db_path)
    app.run(host="127.0.0.1", port=port, debug=False)
