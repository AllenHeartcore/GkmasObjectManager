"""
server.py
Flask web server entry point.
"""

from datetime import datetime, timedelta, timezone

from flask import Flask, Response, jsonify, render_template, request

import GkmasObjectManager as gom
from GkmasObjectManager.manifest import GkmasManifest

app = Flask(__name__)
m = None


def _get_manifest() -> GkmasManifest:
    global m
    if m is None:
        m = gom.fetch()
    return m


def _sanitize_mtime(mtime: float) -> str:
    mtime = datetime.fromtimestamp(mtime, tz=timezone.utc)
    mtime = mtime.astimezone(timezone(timedelta(hours=9)))  # Japan Standard Time
    return mtime.strftime("%Y-%m-%d %H:%M:%S")


# API endpoints


@app.route("/api/manifest")
def api_manifest() -> Response:
    return jsonify(_get_manifest()._get_canon_repr())


@app.route("/api/search")
def api_search() -> Response:
    query = request.args.get("query", "")
    return jsonify(
        [
            {
                "id": obj.id,
                "name": obj.name,
                "type": type(obj).__name__[5:],  # valid names start with "Gkmas"
            }
            for obj in _get_manifest().search(
                "".join(f"(?=.*{word})" for word in query.split())
                # use lookahead to match all words in any order
            )
        ]
    )


@app.route("/api/assetbundle/<id>/bytestream")
def api_assetbundle_bytestream(id: str) -> Response:
    obj = _get_manifest().assetbundles[int(id)]
    data = obj.get_data()
    return Response(
        data["bytes"],
        mimetype=data["mimetype"],
        headers={"Last-Modified": _sanitize_mtime(data["mtime"])},
    )


@app.route("/api/resource/<id>/bytestream")
def api_resource_bytestream(id: str) -> Response:
    obj = _get_manifest().resources[int(id)]
    data = obj.get_data()
    return Response(
        data["bytes"],
        mimetype=data["mimetype"],
        headers={"Last-Modified": _sanitize_mtime(data["mtime"])},
    )


# Frontend routes


@app.route("/")
def home() -> str:
    return render_template("home.html")


@app.route("/search")
def search() -> str:
    return render_template(
        "search.html",
        query=request.args.get("query", ""),
        byID=request.args.get("byID", "true") == "true",
        ascending=request.args.get("ascending", "false") == "true",
        entriesPerPage=int(request.args.get("entriesPerPage", 12)),
        currentPage=int(request.args.get("currentPage", 1)),
    )


@app.route("/view/assetbundle/<id>")
def view_assetbundle(id: str) -> str:

    try:
        obj = _get_manifest().assetbundles[int(id)]
    except KeyError:
        return render_template("404.html"), 404

    info = obj._get_canon_repr()
    info["raw_url"] = obj._url
    if "dependencies" in info:
        info["dependencies"] = [
            {
                "id": dep,
                "name": _get_manifest().assetbundles[int(dep)].name,
            }
            for dep in info["dependencies"]
        ]
    return render_template("view.html", info=info, type="AssetBundle")


@app.route("/view/resource/<id>")
def view_resource(id: str) -> str:

    try:
        obj = _get_manifest().resources[int(id)]
    except KeyError:
        return render_template("404.html"), 404

    info = obj._get_canon_repr()
    info["raw_url"] = obj._url
    return render_template("view.html", info=info, type="Resource")


@app.errorhandler(404)
def page_not_found(error: Exception) -> tuple[str, int]:
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(port=8080)
