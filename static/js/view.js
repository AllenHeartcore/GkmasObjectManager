let acb_basename = "";
let acb_aliases = [];

function viewMediaPopulator(media, url, mimetype, mtime) {
    $("#uploadTime").text(mtime);

    if (mimetype.startsWith("image/")) {
        media.append($("<img>").attr("src", url).attr("alt", info.name));
    } else if (mimetype.startsWith("audio/")) {
        media.append(
            $("<audio>")
                .attr({ src: url, controls: true })
                .attr("alt", info.name)
        );
    } else if (mimetype.startsWith("video/")) {
        media.append(
            $("<video>")
                .attr({ src: url, controls: true })
                .attr("alt", info.name)
        );
    } else if (mimetype === "application/zip") {
        // an archive of WAV files (subsongs extracted from .acb)
        media.addClass("overflow-y-auto w-100");

        fetch(url)
            .then((response) => response.blob())
            .then((blob) => JSZip.loadAsync(blob))
            .then((zip) => {
                Object.keys(zip.files).forEach((filename) => {
                    let row = $("<div>").addClass(
                        "row align-center my-2 mx-5 gx-0"
                    );
                    let col1 = $("<div>").addClass("col-2 text-start fs-5");
                    let col2 = $("<div>").addClass("col-10 text-end fs-5");
                    let col3 = $("<div>").addClass("col-12 mb-3");

                    let alias = filename.split(".")[0];
                    if (filename.startsWith(acb_basename)) {
                        alias = alias.slice(acb_basename.length + 1);
                    } else {
                        console.warn(
                            "Subsong basename mismatch: expected",
                            acb_basename,
                            "but got",
                            filename
                        );
                    }

                    acb_aliases.push(alias);
                    col1.text(alias);
                    col2.attr("id", "caption_" + alias).text(
                        "Loading caption..."
                    );

                    zip.files[filename].async("blob").then((fblob) => {
                        fblob = new Blob([fblob], { type: "audio/wav" });
                        const furl = URL.createObjectURL(fblob);
                        col3.append(
                            $("<audio>")
                                .attr({ src: furl, controls: true })
                                .attr("alt", filename)
                                .addClass("w-100")
                        );
                    });

                    row.append(col1).append(col2).append(col3);
                    media.append(row);
                });
                populateCaption();
            });
    } else {
        handleUnsupportedMedia(url);
        return;
    }

    $("#downloadConvertedMedia")
        .text("Download Converted " + mimetype.split("/")[1].toUpperCase())
        .attr("href", url)
        .attr("download", info.name.replace(/\.[^/.]+$/, ""))
        .removeClass("disabled");
}

function populateCaption() {
    $.ajax({
        url: "/api/caption_map/" + info.name,
        type: "GET",
        dataType: "json",
        contentType: "application/json; charset=utf-8",
        success: function (data) {
            acb_aliases.forEach((alias) => {
                let captionElt = $("#caption_" + alias);
                if (data["error"]) {
                    captionElt.text("ERROR: " + data["error"]);
                } else if (data[acb_basename + "_" + alias]) {
                    captionElt.text(data[acb_basename + "_" + alias]);
                } else {
                    captionElt.text("ERROR: Caption not found");
                }
            });
        },
        error: function (...args) {
            dumpErrorToConsole(...args);
        },
    });
}

function handleUnsupportedMedia(url) {
    $("#viewMediaContent").append(
        $("<div>").text("Preview not available for this type of media.")
    );
    if (type === "AssetBundle") {
        $("#downloadConvertedMedia")
            .text("Deobfuscated AssetBundle")
            .attr("href", url)
            .attr("download", info.name.replace(/\.[^/.]+$/, "") + ".unity3d")
            .removeClass("disabled");
    } else {
        $("#downloadConvertedMedia")
            .text("Conversion Unavailable")
            .removeClass("btn-primary")
            .addClass("btn-secondary");
    }
}

$(document).ready(function () {
    acb_basename = info.name.split(".")[0];
    setAccentColorByString(info.name);
    progressedMediaDriver(type, info.id, $("#viewMedia"), viewMediaPopulator);
});
