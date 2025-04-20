const ACCENT_COLORS = {
    "hski": "#FF4F64",
    "ttmr": "#27B4EB",
    "fktn": "#FFD203",
    "hrnm": "#FD7EC2",
    "ssmk": "#92DE5A",
    "shro": "#00BED8",
    "kllj": "#D2E3E4",
    "kcna": "#FE8A22",
    "amao": "#C45DC8",
    "hume": "#F74C2C",
    "hmsz": "#6EA3FC",
    "jsna": "#FFAC28",
    "nasr": "#8D6C71",
};

const HUE_GRADIENT_VARIANCE = 18;

function hex2rgb(hex) {
    return [
        parseInt(hex.slice(1, 3), 16),
        parseInt(hex.slice(3, 5), 16),
        parseInt(hex.slice(5, 7), 16),
    ];
}

function rgb2hsl(r, g, b) {
    r /= 255;
    g /= 255;
    b /= 255;
    let max = Math.max(r, g, b);
    let min = Math.min(r, g, b);
    let h,
        s,
        l = (max + min) / 2;
    if (max == min) {
        h = s = 0;
    } else {
        let d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r:
                h = (g - b) / d + (g < b ? 6 : 0);
                break;
            case g:
                h = (b - r) / d + 2;
                break;
            case b:
                h = (r - g) / d + 4;
                break;
        }
        h /= 6;
    }
    return [h, s, l];
}

function findAccentColorKey(str) {
    const keysPattern = Object.keys(ACCENT_COLORS).join("|");
    const regex = new RegExp(`\\b(${keysPattern})\\b`); // ensure whole word match
    const match = str.replace(/_/g, "-").match(regex); // _ is not a word boundary
    return match ? match[1] : "";
}

function setAccentColorByKey(key) {
    let accent = ACCENT_COLORS[key];
    let hsl = rgb2hsl(...hex2rgb(accent));

    let baseHue = hsl[0] * 360;
    let leftHue = (baseHue - HUE_GRADIENT_VARIANCE + 360) % 360; // prevent underflow
    let rightHue = (baseHue + HUE_GRADIENT_VARIANCE) % 360;

    // navbar
    $("#navbarSticker").attr({
        "src": `/static/img/face/${key}.png`,
        "alt": `Sticker of ${CHARACTER_ALIAS[key]}`,
    });
    $(".navbar").css(
        "background-color",
        `hsl(${baseHue}, ${hsl[1] * 100}%, 90%)`
    );
    $("#navbarText").css("color", `hsl(${baseHue}, 50%, 50%)`);

    // homepage
    $(".text-gradient").css(
        "background-image",
        `linear-gradient(to right, hsl(${leftHue}, 70%, 50%), hsl(${rightHue}, 70%, 50%))`
    );
}

function setAccentColorByString(str) {
    let key = findAccentColorKey(str);
    if (key) setAccentColorByKey(key);
}

function setRandomAccentColor() {
    let keys = Object.keys(ACCENT_COLORS);
    let key = keys[Math.floor(Math.random() * keys.length)];
    setAccentColorByKey(key);
}
