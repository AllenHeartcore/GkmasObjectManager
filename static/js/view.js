function displayMedia() {
    getMediaBlobURL(type, info.id).then(({ url, mimetype, mtime }) => {
        $("#uploadTime").text(mtime);
        $("#loadingSpinnerMedia").hide();
        $("#viewMediaContent").show();
        let container = $("#viewMediaContent");

        if (mimetype.startsWith("image/")) {
            container.append(
                $("<img>").attr("src", url).attr("alt", info.name)
            );
        } else if (mimetype.startsWith("audio/")) {
            container.append(
                $("<audio>")
                    .attr({ src: url, controls: true })
                    .attr("alt", info.name)
            );
        } else if (mimetype.startsWith("video/")) {
            container.append(
                $("<video>")
                    .attr({ src: url, controls: true })
                    .attr("alt", info.name)
            );
        } else if (mimetype === "application/zip") {
            // an archive of WAV files (subsongs extracted from .acb)
            $("#viewMediaContent").addClass("vertically-scrollable");

            fetch(url)
                .then((response) => response.blob())
                .then((blob) => JSZip.loadAsync(blob))
                .then((zip) => {
                    Object.keys(zip.files).forEach((filename) => {
                        let row = $("<div>").addClass(
                            "row align-center my-2 gx-0"
                        );
                        let col0 = $("<div>").addClass("col-1");
                        let col1 = $("<div>").addClass("col-2 align-left fs-5");
                        let col2 = $("<div>").addClass("col-9");

                        let alias = filename.split(".")[0].split("_").pop();
                        col1.text(alias);

                        zip.files[filename].async("blob").then((fblob) => {
                            fblob = new Blob([fblob], { type: "audio/wav" });
                            const furl = URL.createObjectURL(fblob);
                            col2.append(
                                $("<audio>")
                                    .attr({ src: furl, controls: true })
                                    .attr("alt", filename)
                            );
                        });

                        row.append(col0).append(col1).append(col2);
                        container.append(row);
                    });
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
    setAccentColorByString(info.name);
    displayMedia();
});
