function displayMedia() {
    getMediaBlobURL(type, info.id).then(({ url, mimetype }) => {
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
