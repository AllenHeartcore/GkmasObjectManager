const MEDIA_ALIAS = {
    "img": "Image",
    "sud": "Audio",
    "mov": "Video",
    "adv": "Story",
    "mdl": "Model",
    "mot": "Motion",
    "env": "Environment",
    "fbx": "FBX",
};

const SUBTYPE_ALIAS = {
    "cidol full": "Idol Card",
    "csprt full": "Support Card",
    "story-bg": "Background",
    "meishi_base full": "Namecard Bg",
    "pdrink": "P Drink",
    "pitem": "P Item",
    "skillcard": "Skillcard",
    "meishi_illust": "Namecard Elt",
};

const CHARACTER_ALIAS = {
    "hski": "Hanami Saki",
    "ttmr": "Tsukimura Temari",
    "fktn": "Fujita Kotone",
    "amao": "Arimura Mao",
    "kllj": "Katsuragi Lilja",
    "kcna": "Kuramoto China",
    "ssmk": "Shiun Sumika",
    "shro": "Shinosawa Hiro",
    "hrnm": "Himesaki Rinami",
    "hume": "Hanami Ume",
    "hmsz": "Hataya Misuzu",
    "jsna": "Juo Sena",
    "nasr": "Neo Asari",
};

const RARITY_ALIAS = {
    "-1-": "R",
    "-2-": "SR",
    "-3-": "SSR",
};

const SONG_ALIAS = {
    "all -001": "初",
    "all -002": "Campus mode!!",
    "all -003": "キミとセミブルー",
    "all -004": "冠菊",
    "all -005": "仮装狂騒曲",
    "all -006": "White Night! White Wish!",
    "all -007": "ハッピーミルフィーユ",
    "all -008": "古今東西ちょちょいのちょい",
    "all -009": "雪解けに",
    "char -001": "(1st Single)",
    "char -002": "(2nd Single)",
    "char -003": "(2024-25 Birthday Song)",
};

function dumpErrorToConsole(...args) {
    var name_of_parent_function = arguments.callee.caller.name;
    console.error("Error in " + name_of_parent_function);
    args.forEach((arg) => {
        console.error(arg);
    });
}

/*
    The two drivers below expect a rigid class structure in the container:
        media-container  (handled by progressedMediaDriver)
        - prog-container (handled by progressDriver)
        - - prog-stage
        - - prog-num
        - - prog-bar-container
        - - - prog-bar
        - media-content
*/

function progressedMediaDriver(type, id, container, mediaPopulator) {
    const progress = container.find(".prog-container");
    const media = container.find(".media-content");
    let sse_src = progressDriver(type, id, progress, media);
    getMediaBlobURL(type, id)
        .then(({ url, mimetype, mtime }) => {
            sse_src.close();
            progress.hide();
            media.show();
            mediaPopulator(media, url, mimetype, mtime);
        })
        .catch((error) => {
            sse_src.close();
            progress.hide();
            media.show();
            media.text("Failed to load media: " + error.message);
            dumpErrorToConsole(error);
        });
}

function progressDriver(type, id, progress, media) {
    const src = new EventSource(`/sse/${type.toLowerCase()}/${id}/progress`);

    src.onopen = function () {
        progress.show();
        media.hide();
    };

    src.onerror = function (event) {
        progress
            .find(".prog-stage")
            .text("ERROR: Cannot subscribe to progress stream");
        progress.find(".prog-num").text("");
        progress.find(".prog-bar-container").hide();
        dumpErrorToConsole(event);
        src.close();
    };

    src.onmessage = function (event) {
        const data = JSON.parse(event.data);
        progress.find(".prog-stage").text(data.stage + "...");
        progress.find(".prog-num").text(data.completed + " / " + data.total);
        progress
            .find(".prog-bar")
            .css("width", (data.completed / data.total) * 100 + "%");
    };

    src.addEventListener("success", function (event) {
        const data = JSON.parse(event.data);
        progress.find(".prog-stage").text(data.message);
        progress.find(".prog-num").text("");
        progress.find(".prog-bar").css("width", "100%");
        src.close();
    });

    src.addEventListener("warning", function (event) {
        const data = JSON.parse(event.data);
        progress.find(".prog-stage").text("WARNING: " + data.message);
        console.warn(data.message);
    });

    src.addEventListener("error", function (event) {
        const data = JSON.parse(event.data);
        progress.find(".prog-stage").text("ERROR: " + data.message);
        progress.find(".prog-num").text("");
        progress.find(".prog-bar-container").hide();
        dumpErrorToConsole(event);
        src.close();
    });

    return src; // for external access
}

function getMediaBlobURL(type, id) {
    return new Promise((resolve, reject) => {
        $.ajax({
            type: "GET",
            url: `/api/${type.toLowerCase()}/${id}/bytestream`,
            xhrFields: { responseType: "arraybuffer" },

            success: function (data, status, request) {
                const mimetype = request.getResponseHeader("Content-Type");
                const mtime = request.getResponseHeader("Last-Modified");
                blob = new Blob([data], { type: mimetype });
                resolve({
                    url: URL.createObjectURL(blob),
                    mimetype: mimetype,
                    mtime: mtime.replace(/ GMT.*/, ""),
                });
            },

            error: function (...args) {
                dumpErrorToConsole(...args);
                blob = new Blob(["An error occurred while fetching media."], {
                    type: "text/plain",
                });
                reject({
                    url: URL.createObjectURL(blob),
                    mimetype: "text/plain",
                    mtime: "Unknown",
                });
            },
        });
    });
}
