"""
server.py
Flask web server entry point.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from queue import Queue
from typing import Optional, Union

from flask import Flask, Response, jsonify, render_template, request

import GkmasObjectManager as gom
from GkmasObjectManager.manifest import GkmasManifest
from GkmasObjectManager.object import GkmasAssetBundle, GkmasResource

# bookkeeping & helpers

app = Flask(__name__)
queues = defaultdict(Queue)
m = None


def _get_manifest() -> GkmasManifest:
    global m
    if m is None:
        m = gom.fetch()
    return m


def _get_object(
    type: str, id: Union[int, str]
) -> Union[GkmasAssetBundle, GkmasResource]:
    m = _get_manifest()

    try:
        id = int(id)
    except ValueError:
        pass

    if type == "assetbundle":
        return m.assetbundles[id]
    elif type == "resource":
        return m.resources[id]
    else:
        raise ValueError(f"Unknown type: {type}")


def _sanitize_mtime(mtime: float) -> str:
    mtime = datetime.fromtimestamp(mtime, tz=timezone.utc)
    mtime = mtime.astimezone(timezone(timedelta(hours=9)))  # Japan Standard Time
    return mtime.strftime("%Y-%m-%d %H:%M:%S")


# API endpoints


@app.route("/api/manifest")
def api_manifest() -> Response:
    return jsonify(_get_manifest().canon_repr)


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


@app.route("/api/<type>/<id>/bytestream")
def api_bytestream(type: str, id: str) -> Response:

    try:
        obj = _get_object(type, id)
    except (ValueError, KeyError):
        return jsonify({"error": "Object not found"})

    q = queues[(type, id)]
    data = obj.get_data(upstream=q)
    obj._reporter.success("Data ready at frontend")

    return Response(
        data["bytes"],
        mimetype=data["mimetype"],
        headers={"Last-Modified": _sanitize_mtime(data["mtime"])},
    )


@app.route("/api/caption_map/<name>")
def api_caption_map(name: str) -> Response:
    try:
        ret = _get_object(
            "resource", name.replace("sud_vo_", "").replace(".acb", ".txt")
        ).media.caption_map
    except KeyError:
        ret = {"error": "Caption not found"}
    except AttributeError:
        ret = {"error": "Caption not supported"}
    except ValueError:
        ret = {"error": "Caption loading failed"}
    return jsonify(ret)


# SSE endpoints


def _poll_and_format(type: str, id: str) -> str:

    event: str = ""
    data: dict = {}
    q: Optional[Queue[dict]] = None

    q = queues[(type, id)]

    try:
        progress: dict = q.get(timeout=1)
    except Exception:
        return ":keep-alive\n\n"  # no new data, keep connection alive
    if not progress:
        event = "error"
        data = {"message": "Progress stream is empty"}
    else:
        event = progress.pop("event", event)
        data = progress.copy()

    ret = f"event: {event}\n" if event else ""
    ret += f"data: {json.dumps(data)}\n\n"
    return ret


@app.route("/sse/<type>/<id>/progress")
def sse_progress(type: str, id: str) -> Response:

    def generate():
        while True:
            yield _poll_and_format(type, id)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
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


@app.route("/view/<type>/<id>")
def view(type: str, id: str) -> str:

    if type == "assetbundle":
        type_display = "AssetBundle"
    elif type == "resource":
        type_display = "Resource"
    else:
        return render_template("404.html")

    try:
        obj = _get_object(type, id)
    except (ValueError, KeyError):
        return render_template("404.html")

    info = obj.canon_repr
    info["raw_url"] = obj._url
    if "dependencies" in info:
        info["dependencies"] = [
            {
                "id": dep,
                "name": _get_object(type, dep).name,  # error handling?
            }
            for dep in info["dependencies"]
        ]

    return render_template("view.html", info=info, type=type_display)


@app.errorhandler(404)
def page_not_found(error: Exception) -> tuple[str, int]:
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(port=8080)
