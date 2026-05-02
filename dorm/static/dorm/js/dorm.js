(function () {
    "use strict";

    const layout   = document.getElementById("dorm-layout");
    const paneA    = document.getElementById("dorm-pane-a");
    const divider  = document.getElementById("dorm-divider");
    const verboseCb = document.getElementById("dorm-verbose-cb");

    let isResizing = false;
    let startPos   = 0;
    let startSize  = 0;

    // ── Layout toggle ─────────────────────────────────────────

    window.dormSetLayout = function (dir) {
        layout.dataset.dir = dir;
        paneA.style.flex   = "0 0 50%";
        document.querySelectorAll(".dorm-layout-opt").forEach(function (btn) {
            btn.classList.toggle("active", btn.dataset.dir === dir);
        });
    };

    // ── Verbose names toggle ──────────────────────────────────

    function applyVerbose() {
        var useVerbose = verboseCb ? verboseCb.checked : true;
        document.querySelectorAll(".dorm-table th").forEach(function (th) {
            th.textContent = useVerbose ? th.dataset.verbose : th.dataset.field;
        });
    }

    if (verboseCb) {
        verboseCb.addEventListener("change", applyVerbose);
    }

    // Re-apply after each htmx result swap
    document.body.addEventListener("htmx:afterSwap", applyVerbose);

    // ── CSV / JSON export ─────────────────────────────────────

    window.dormExport = function (format) {
        var table = document.querySelector(".dorm-table");
        if (!table) return;

        var headers = Array.from(table.querySelectorAll("thead th"))
                          .map(function (th) { return th.textContent.trim(); });

        var rows = Array.from(table.querySelectorAll("tbody tr"))
                       .map(function (tr) {
                           return Array.from(tr.querySelectorAll("td"))
                                       .map(function (td) { return td.textContent.trim(); });
                       });

        var model   = (table.dataset.model || "dorm") + "_records";
        var content, filename, mime;

        if (format === "csv") {
            var esc = function (v) { return '"' + v.replace(/;/g, '').replace(/"/g, '""') + '"'; };
            content  = [headers.map(esc).join(";")]
                           .concat(rows.map(function (r) { return r.map(esc).join(";"); }))
                           .join("\n");
            filename = model + ".csv";
            mime     = "text/csv;charset=utf-8;";
        } else {
            var data = rows.map(function (row) {
                var obj = {};
                headers.forEach(function (h, i) { obj[h] = row[i]; });
                return obj;
            });
            content  = JSON.stringify(data, null, 2);
            filename = model + ".json";
            mime     = "application/json";
        }

        var blob = new Blob([content], { type: mime });
        var url  = URL.createObjectURL(blob);
        var a    = document.createElement("a");
        a.href     = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };

    // ── Resize drag ───────────────────────────────────────────

    divider.addEventListener("mousedown", function (e) {
        isResizing = true;
        var isRow  = layout.dataset.dir === "row";
        startPos   = isRow ? e.clientX : e.clientY;
        startSize  = isRow ? paneA.offsetWidth : paneA.offsetHeight;
        document.body.classList.add(isRow ? "is-resizing-row" : "is-resizing-col");
        e.preventDefault();
    });

    document.addEventListener("mousemove", function (e) {
        if (!isResizing) return;
        var isRow     = layout.dataset.dir === "row";
        var pos       = isRow ? e.clientX : e.clientY;
        var delta     = pos - startPos;
        var container = isRow ? layout.offsetWidth : layout.offsetHeight;
        var newSize   = Math.max(80, Math.min(startSize + delta, container - 85));
        paneA.style.flex = "0 0 " + newSize + "px";
    });

    document.addEventListener("mouseup", function () {
        if (!isResizing) return;
        isResizing = false;
        document.body.classList.remove("is-resizing-row", "is-resizing-col");
    });

    // ── Ctrl+Enter submit ─────────────────────────────────────

    document.addEventListener("keydown", function (e) {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            var form = document.getElementById("dorm-form");
            if (form) {
                e.preventDefault();
                htmx.trigger(form, "submit");
            }
        }
    });

}());
