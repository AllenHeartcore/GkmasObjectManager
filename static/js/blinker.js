const BLINKING_INTERVAL = 500; // milliseconds

$(document).ready(function () {
    // initial state
    let blinkState = false;
    let blinkerElt = $("#loadingBlinkerImage");
    blinkerElt.attr("src", "/static/img/figure/" + accentColorKey + ".png");

    // animation loop
    setInterval(() => {
        blinkerElt.attr(
            "src",
            blinkState
                ? "/static/img/figure/" + accentColorKey + ".png"
                : "/static/img/figure/" + accentColorKey + "_alt.png"
        );
        blinkState = !blinkState;
    }, BLINKING_INTERVAL);
});
