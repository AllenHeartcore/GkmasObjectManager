import GkmasObjectManager as gom

import re
import html
from flask import Flask, render_template, request, jsonify, Response


# Bookkeeping


app = Flask(__name__)
m = None


def _get_manifest():
    global m
    if m is None:
        m = gom.load("manifest.json")
    return m


# API endpoints


@app.route("/api/manifest")
def api_manifest():
    return jsonify(_get_manifest()._get_canon_repr())


@app.route("/api/search")
def api_search():
    query = request.args.get("query", "")
    tokens = re.findall(r'"[^"]+"|\S+', html.unescape(query))
    return jsonify(
        [
            _get_manifest()[id]._get_canon_repr()
            for id in set.intersection(  # targets satisfy ALL conditions
                *[
                    _get_manifest().search(f".*{token.strip('\"')}.*")
                    for token in tokens  # for each condition
                ]
            )
        ]
    )


@app.route("/api/update/<id>", methods=["POST"])
def api_update(id):
    data = request.get_json()
    _get_manifest().update(int(id), data)
    return Response(status=200)


# Frontend routes


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/search")
def search():
    query = request.args.get("query", "")
    return render_template("search.html", query=query)


@app.route("/view/<id>")
def view(id):

    try:
        obj = _get_manifest().resources[int(id)]
    except KeyError:
        return render_template("404.html"), 404

    info = obj._get_canon_repr()
    return render_template("view.html", info=info, type="Resource")


@app.route("/add")
def add():
    return render_template(
        "editor.html",
        edit_mode=False,
        info={
            "id": _get_manifest()._get_largest_id() + 1,
            "name": "",
            "size": "Unknown",
            "md5": "Unknown",
            "url": "",
            "cover": "",
            "keywords": [],
            "caption": "",
            # this is neater than writing sanity checks in the template
        },
        type="Resource",
    )


@app.route("/edit/<id>")
def edit(id):

    try:
        obj = _get_manifest().resources[int(id)]
    except KeyError:
        return render_template("404.html"), 404

    info = obj._get_canon_repr()
    return render_template("editor.html", edit_mode=True, info=info, type="Resource")


@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(port=8080)
