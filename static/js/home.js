const WALLPAPER_REGEX_PATTERN =
    /^img_general_(cidol.*1-thumb-landscape-large|(csprt|meishi_base).*full)$/;
const NUM_FEATURED_SAMPLES = 24;

function populateHomepageContainers(data) {
    $("#homeMetadataRevision").text(data.revision);
    $("#homeMetadataAbCount").text(data.assetBundleList.length);
    $("#homeMetadataResCount").text(data.resourceList.length);

    let matches = data.assetBundleList
        .filter((ab) => WALLPAPER_REGEX_PATTERN.test(ab.name))
        .map((ab) => ({ id: ab.id, name: ab.name }));

    let latestSamples = matches
        .sort((a, b) => b.id - a.id)
        .slice(0, NUM_FEATURED_SAMPLES);

    // Pre-populate with empty divs for indexing
    let container = $("#homeFeaturedContainer");
    for (let i = 0; i < NUM_FEATURED_SAMPLES; i++) {
        container.append($("<div>").addClass("col-md-2 mt-3 "));
    }

    // Place images in the correct order since Promise's are async
    latestSamples.forEach((item, index) => {
        getMediaBlobURL("AssetBundle", item.id).then(({ url, mimetype, _ }) => {
            if (!mimetype.startsWith("image/")) {
                console.log(
                    `Expected an image mimetype for asset ${item.id}, but got ${mimetype}`
                );
                return;
            }
            let image = $("<img>")
                .attr("src", url)
                .attr("alt", item.name)
                .addClass("image-landscape image-roundedge shadow-at-hover");
            let link = $("<a>")
                .attr("href", `/view/assetbundle/${item.id}`)
                .append(image);
            container.children().eq(index).append(link);
        });
    });

    $("#loadingSpinner").hide();
    $("#homepageElements").show();
}

function reportHomepageError() {
    $("#loadingSpinner").hide();
    $("#homeMetadata").html(`
        GkmasManifest cannot be fetched. <br>
        Check Internet connection. <br>
        Refresh to retry.
    `);
}

$(document).ready(function () {
    $("#navbarNav").children("#searchForm").remove();

    $.ajax({
        type: "GET",
        url: "/api/manifest",
        dataType: "json",
        contentType: "application/json; charset=utf-8",
        success: function (result) {
            populateHomepageContainers(result);
        },
        error: function (...args) {
            dumpErrorToConsole(...args);
            reportHomepageError();
        },
    });

    $("#homeGotoForm").submit(function (event) {
        event.preventDefault();
        // sanitize user input, suppress 'DOM text reinterpreted as HTML' in CodeQL
        let id = encodeURIComponent($("#homeGotoInput").val());
        let type = encodeURIComponent($("#homeGotoType").val());
        window.location.href = `/view/${type}/${id}`;
    });

    $("#homeGotoInput").keydown(function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            $("#homeGotoForm").submit();
        }
    });
});
