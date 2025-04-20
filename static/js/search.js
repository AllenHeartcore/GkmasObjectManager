// We keep these vars global to avoid passing them around
let searchEntries = []; // this can be huge (up to ~10k entries)
let sortState = {
    byID: null,
    ascending: null,
};
/*  Even though backend returns entries by ascending name,
    it's more extensible to avoid hardcoding this assumption,
    since we now force a sort at initial display.
    (Sorting by large amounts is made possible by pagination,
    which removes the overhead of *displaying* them all at once.)
*/

// highlighting support
let tokens = [];

// pagination support
const PAGE_NAV_CONTEXT_SIZE = 1;
var entriesPerPage = 12;
var currentPage = 1;
var totalPages = 0;

/*  CONTROL FLOW:
    $(document).ready
        -> populateSearchpageContainers
        -> sortSearchEntries, updateEpp
    updateSort
        -> sortSearchEntries, updatePageState
    updateEpp
        -> updatePageState
    updatePageState
        -> refreshCardContainer
        -> updatePagination, highlightTokens
    updatePagination
        -> appendPaginationButton

                   US - SSE
                      X
    [init] - PSC ----/  UPS - RCC - UP - APB
                 \    /           \
                   UE               HT
*/

function appendPaginationButton(text, isEnabled, pageUpdater) {
    $("#paginationContainer").append(
        $("<button>")
            .addClass("btn btn-primary mx-1")
            .text(text)
            .prop("disabled", !isEnabled)
            .click(() => {
                currentPage = pageUpdater(currentPage);
                updatePageState();
            })
    );
}

function updatePagination() {
    totalPages = Math.ceil(searchEntries.length / entriesPerPage);
    $("#paginationContainer").empty();

    // Prev  [1]    2                      ...    N   Next
    // Prev   1    [2]    3                ...    N   Next
    // Prev   1     2    [3]    4          ...    N   Next
    // Prev   1    ...    3    [4]    5    ...    N   Next
    // Prev   1    ...   I-1   [I]   I+1   ...    N   Next
    // Prev   1    ...   N-4  [N-3]  N-2   ...    N   Next
    // Prev   1    ...         N-3  [N-2]  N-1    N   Next
    // Prev   1    ...               N-2  [N-1]   N   Next
    // Prev   1    ...                     N-1   [N]  Next

    // head
    appendPaginationButton("Prev", currentPage > 1, (page) => page - 1);
    appendPaginationButton("1", currentPage !== 1, () => 1);

    if (totalPages <= PAGE_NAV_CONTEXT_SIZE * 2 + 1) {
        // no need for ellipsis, display all buttons
        for (let i = 2; i <= totalPages; i++) {
            appendPaginationButton(i.toString(), currentPage !== i, () => i);
        }
    } else {
        // leading ellipsis
        if (currentPage > PAGE_NAV_CONTEXT_SIZE + 2) {
            $("#paginationContainer")
                .append($("<span>").text("..."))
                .addClass("mx-2");
        }

        // context
        let start = Math.max(currentPage - PAGE_NAV_CONTEXT_SIZE, 2);
        let end = Math.min(currentPage + PAGE_NAV_CONTEXT_SIZE, totalPages - 1);
        for (let i = start; i <= end; i++) {
            appendPaginationButton(i.toString(), currentPage !== i, () => i);
        }

        // trailing ellipsis
        if (currentPage < totalPages - PAGE_NAV_CONTEXT_SIZE - 1) {
            $("#paginationContainer")
                .append($("<span>").text("..."))
                .addClass("mx-2");
        }

        // tail
        appendPaginationButton(
            totalPages.toString(),
            currentPage !== totalPages,
            () => totalPages
        );
    }

    appendPaginationButton(
        "Next",
        currentPage < totalPages && totalPages > 0,
        (page) => page + 1
    );
}

function highlightTokens(text) {
    if (tokens.length === 0) {
        return text;
    }
    let regex = new RegExp(`(${tokens.join("|")})`, "gi");
    return text.replace(regex, '<mark class="bg-warning">$1</mark>');
}

function refreshCardContainer() {
    $("#searchEntryCardContainer").empty();

    let start = (currentPage - 1) * entriesPerPage;
    let end = Math.min(currentPage * entriesPerPage, searchEntries.length);
    let pageEntries = searchEntries.slice(start, end);

    pageEntries.forEach((entry) => {
        let card = $("<div>")
            .addClass("card shadow-at-hover")
            .attr("id", "searchEntryCard");
        if (entry.name.startsWith("img_")) {
            getMediaBlobURL(entry.type, entry.id).then(
                ({ url, mimetype, _ }) => {
                    card.prepend(
                        $("<img>")
                            .addClass("card-img-top")
                            .attr("id", "searchEntryCardImage")
                            .attr("src", url)
                            .attr("alt", entry.name)
                    );
                }
            );
        }
        card.append(
            $("<div>")
                .addClass("card-body")
                .append(
                    $("<div>")
                        .addClass("fs-3")
                        .text(`${entry.type} #${entry.id}`),
                    $("<div>")
                        .addClass("fs-6 lh-1")
                        .html(highlightTokens(entry.name))
                )
        );
        let anchor = $("<a>")
            .attr("href", `/view/${entry.type.toLowerCase()}/${entry.id}`)
            .addClass("anchor-no-decoration")
            .append(card);
        $("#searchEntryCardContainer").append(
            $("<div>").addClass("col-md-3").append(anchor)
        );
    });

    updatePagination();
}

function updatePageState() {
    const params = new URLSearchParams(window.location.search);
    params.set("query", $("#searchInput").val().trim());
    params.set("byID", sortState.byID);
    params.set("ascending", sortState.ascending);
    params.set("entriesPerPage", entriesPerPage);
    params.set("currentPage", currentPage);
    window.history.replaceState(
        {},
        "",
        `${window.location.pathname}?${params}`
    );
    refreshCardContainer();
}

function sortSearchEntries() {
    if (sortState.byID) {
        searchEntries.sort((a, b) => {
            // alphabetical order in entry.type implies AssetBundle < Resource
            if (a.type < b.type) return -1;
            if (a.type > b.type) return 1;
            return a.id - b.id;
        });
    } else {
        searchEntries.sort((a, b) => {
            return a.name.localeCompare(b.name);
        });
    }
    if (!sortState.ascending) {
        searchEntries.reverse();
    }
}

function updateSort() {
    let byID_new = $("#sortByID").is(":checked");
    let ascending_new = $("#sortAsc").is(":checked");
    if (byID_new === sortState.byID && ascending_new === sortState.ascending) {
        return;
    }

    sortState.byID = byID_new;
    sortState.ascending = ascending_new;
    sortSearchEntries();

    currentPage = 1;
    updatePageState();
}

function updateEpp(resetPage = true) {
    $("#eppValue").text(entriesPerPage);

    if (entriesPerPage <= 12) {
        $("#eppMinus").prop("disabled", true);
    } else {
        $("#eppMinus").prop("disabled", false);
    }
    if (entriesPerPage >= 96) {
        $("#eppPlus").prop("disabled", true);
    } else {
        $("#eppPlus").prop("disabled", false);
    }

    // If new EPP is non-devisible by old EPP,
    // we're unclear about which page we are currently on.
    if (resetPage) currentPage = 1;
    updatePageState();
}

function populateSearchpageContainers(queryDisplay) {
    $("#searchResultTitle").text(`Search results for "${queryDisplay}"`);

    if (searchEntries.length === 0) {
        $("#searchResultDigest").text("No results found.");
        $("#searchEntryCardContainer").hide();
        $("#paginationContainer").hide();
    } else {
        $("#searchResultDigest").text(
            `Found ${searchEntries.length}` +
                (searchEntries.length === 1 ? " entry." : " entries.")
        );
        sortSearchEntries();
        updateEpp((resetPage = false));
    }

    $("#loadingSpinner").hide();
    $("#searchpageElements").show();
}

$(document).ready(function () {
    setAccentColorByString(query);
    let queryDisplay = query.trim().replace(/\s+/g, " "); // trimmed, duplicate spaces removed
    $("#searchInput").val(queryDisplay + " "); // allows immediate edit/resubmission
    // search input should be displayed alongside the spinner, before a successful AJAX response

    tokens = queryDisplay.split(/\s+/);

    $.ajax({
        type: "GET",
        url: `/api/search`,
        data: { query: query },
        dataType: "json",
        contentType: "application/json; charset=utf-8",
        success: function (result) {
            searchEntries = result;
            populateSearchpageContainers(queryDisplay); // an extra arg, fine
        },
        error: function (...args) {
            dumpErrorToConsole(...args);
        },
    });

    // the following highlights are onetime inits,
    // as info will be passed backwards from here on
    if (sortState.byID) {
        $("#sortByID").prop("checked", true);
    } else {
        $("#sortByName").prop("checked", true);
    }
    if (sortState.ascending) {
        $("#sortAsc").prop("checked", true);
    } else {
        $("#sortDesc").prop("checked", true);
    }

    $("#sortByID").click(updateSort);
    $("#sortByName").click(updateSort);
    $("#sortAsc").click(updateSort);
    $("#sortDesc").click(updateSort);

    $("#eppMinus").click(() => {
        entriesPerPage = Math.max(entriesPerPage - 12, 12);
        updateEpp();
    });
    $("#eppPlus").click(() => {
        entriesPerPage = Math.min(entriesPerPage + 12, 96);
        updateEpp();
    });
});
