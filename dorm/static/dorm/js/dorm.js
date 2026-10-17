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

    // Truncated results ask whether to export the loaded rows or re-run the
    // query server-side for the full result (see "Export modal" below).
    window.dormExport = function (format) {
        var table = document.querySelector(".dorm-table");
        if (!table) return;
        if (table.dataset.truncated === "true") openExportChoice(format, table);
        else exportLoaded(format, table);
    };

    function downloadBlob(blob, filename) {
        var url = URL.createObjectURL(blob);
        var a   = document.createElement("a");
        a.href     = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    }

    function exportLoaded(format, table) {
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

        downloadBlob(new Blob([content], { type: mime }), filename);
    }

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

    // ── Notebook cells ────────────────────────────────────────
    //
    // Each cell is a CodeMirror editor. Running cell N sends cells 1..N to the
    // server, which executes them in order in one namespace (the "flow") and
    // returns the result of cell N. The last cell is always an empty draft.

    var cellsEl   = document.getElementById("dorm-cells");
    var cellTpl   = document.getElementById("dorm-cell-tpl");
    var resultEl  = document.getElementById("dorm-result");
    var toastEl   = document.getElementById("dorm-toast");
    var csrfInput = cellsEl.querySelector("input[name=csrfmiddlewaretoken]");

    var execCount  = 0;
    var lastFlow   = null;   // cells behind the result currently shown
    var activeCell = null;
    var toastTimer = null;

    function allCells() {
        return Array.from(cellsEl.querySelectorAll(".dorm-cell"));
    }

    function setActive(cell) {
        if (activeCell) activeCell.classList.remove("is-active");
        activeCell = cell;
        if (cell) cell.classList.add("is-active");
    }

    function setPrompt(cell, text) {
        cell.querySelector(".dorm-cell-prompt").textContent = "[" + text + "]";
    }

    function toast(message, isError) {
        toastEl.textContent = message;
        toastEl.classList.toggle("is-error", !!isError);
        toastEl.classList.add("is-visible");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () { toastEl.classList.remove("is-visible"); }, 2200);
    }

    function smartTab(cm) {
        if (cm.somethingSelected()) cm.indentSelection("add");
        else cm.replaceSelection("    ", "end");
    }

    function createCell(code, before) {
        var cell = cellTpl.content.firstElementChild.cloneNode(true);
        cellsEl.insertBefore(cell, before || null);

        var run = function () { runCell(cell); };
        var cm  = CodeMirror(cell.querySelector(".dorm-cell-editor"), {
            value:             code || "",
            mode:              "python",
            indentUnit:        4,
            tabSize:           4,
            lineWrapping:      true,
            viewportMargin:    Infinity,
            autoCloseBrackets: true,
            matchBrackets:     true,
            placeholder:       "# All models are auto-imported — no imports needed\nAuthor.objects.all()",
            extraKeys: {
                "Ctrl-Enter":  run,
                "Cmd-Enter":   run,
                "Shift-Enter": run,
                "Tab":         smartTab,
                "Shift-Tab":   "indentLess",
                "Ctrl-/":      "toggleComment",
                "Cmd-/":       "toggleComment",
                "Alt-Up":      function () { stepRecents(cell, 1); },
                "Alt-Down":    function () { stepRecents(cell, -1); },
            },
        });
        cm.on("focus", function () { setActive(cell); });
        // Any edit that isn't a recents step ends history navigation.
        cm.on("change", function () { if (!cell._recentsStepping) cell._recents = null; });
        cell._cm = cm;

        cell.querySelector(".dorm-cell-actions").addEventListener("click", function (e) {
            var btn = e.target.closest("[data-action]");
            if (!btn) return;
            if (btn.dataset.action === "run")    runCell(cell);
            if (btn.dataset.action === "save")   saveCell(cell);
            if (btn.dataset.action === "remove") removeCell(cell);
        });
        return cell;
    }

    function addDraft() {
        var cell = createCell("");
        cell._cm.focus();
        return cell;
    }

    function post(url, params) {
        return fetch(url, {
            method:  "POST",
            headers: { "X-CSRFToken": csrfInput.value },
            body:    params,
        });
    }

    function runCell(cell) {
        var cells  = allCells();
        var idx    = cells.indexOf(cell);
        var target = cell._cm.getValue();
        if (!target.trim() || cell.dataset.state === "running") return;

        var flow   = cells.slice(0, idx + 1).map(function (c) { return c._cm.getValue(); });
        var params = new URLSearchParams();
        flow.forEach(function (code) { params.append("cells", code); });

        var prevState = cell.dataset.state;
        cell.dataset.state = "running";
        setPrompt(cell, "*");

        post(cellsEl.dataset.runUrl, params)
            .then(function (resp) {
                return resp.text().then(function (html) { return { resp: resp, html: html }; });
            })
            .then(function (r) {
                resultEl.innerHTML = r.html;
                applyVerbose();
                cells.forEach(function (c) {
                    if (c !== cell && c.dataset.state === "error") {
                        c.dataset.state = c._count ? "done" : "draft";
                        setPrompt(c, c._count || " ");
                    }
                });

                recentsCache = null;   // this run is now the newest entry
                cell._recents = null;

                if (r.resp.headers.get("X-Dorm-Status") === "ok") {
                    lastFlow = flow;
                    cell.dataset.state = "done";
                    cell._count = ++execCount;
                    setPrompt(cell, cell._count);
                    // Running the trailing draft commits it and opens a new one.
                    if (cell === allCells().slice(-1)[0]) addDraft();
                    return;
                }

                var errIdx  = parseInt(r.resp.headers.get("X-Dorm-Cell"), 10);
                var errCell = isNaN(errIdx) ? cell : cells[errIdx];
                if (errCell !== cell) {
                    cell.dataset.state = prevState;
                    setPrompt(cell, cell._count || " ");
                }
                errCell.dataset.state = "error";
                setPrompt(errCell, "!");
            })
            .catch(function (err) {
                cell.dataset.state = "error";
                setPrompt(cell, "!");
                toast("Request failed: " + err.message, true);
            });
    }

    function saveCell(cell) {
        var code = cell._cm.getValue().trim();
        if (!code) return toast("Nothing to save", true);

        var suggestion = code.split("\n")[0].slice(0, 40);
        var name = window.prompt("Save command as:", suggestion);
        if (!name || !name.trim()) return;

        var params = new URLSearchParams({ name: name.trim(), code: code });
        post(cellsEl.dataset.saveUrl, params)
            .then(function (resp) { return resp.json(); })
            .then(function (data) {
                if (data.ok) toast("Saved “" + data.name + "”");
                else toast(data.error || "Could not save", true);
            })
            .catch(function () { toast("Could not save", true); });
    }

    function removeCell(cell) {
        var cells = allCells();
        // The trailing draft is never removed, only cleared.
        if (cell === cells[cells.length - 1]) {
            cell._cm.setValue("");
            cell.dataset.state = "draft";
            cell._count = 0;
            setPrompt(cell, " ");
            cell._cm.focus();
            return;
        }
        var next = cells[cells.indexOf(cell) + 1];
        if (activeCell === cell) setActive(null);
        cell.remove();
        next._cm.focus();
    }

    // ── Recents navigation (Alt/Option + Up/Down) ─────────────
    //
    // Shell-style: Up = older, Down = newer. Going back past the newest entry
    // restores what was typed before navigation started.

    var recentsCache   = null;
    var recentsLoading = null;

    function loadRecents() {
        if (recentsCache) return Promise.resolve(recentsCache);
        if (!recentsLoading) {
            recentsLoading = fetch(cellsEl.dataset.historyUrl + "?format=json")
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    recentsCache   = data.recents || [];
                    recentsLoading = null;
                    return recentsCache;
                }, function (err) {
                    recentsLoading = null;
                    throw err;
                });
        }
        return recentsLoading;
    }

    function stepRecents(cell, dir) {
        loadRecents().then(function (list) {
            var cm    = cell._cm;
            var state = cell._recents || { idx: -1, stash: cm.getValue() };
            var next  = state.idx + dir;

            if (next >= list.length) return toast(list.length ? "No older entries" : "No recent executions");
            if (next < -1) return;

            cell._recentsStepping = true;
            cm.setValue(next === -1 ? state.stash : list[next]);
            cell._recentsStepping = false;
            cm.setCursor(cm.lineCount(), 0);

            state.idx     = next;
            cell._recents = next === -1 ? null : state;
        }).catch(function () { toast("Could not load recents", true); });
    }

    window.dormRunActive = function () {
        var cells = allCells();
        runCell(activeCell && cellsEl.contains(activeCell) ? activeCell : cells[cells.length - 1]);
    };

    addDraft();

    // ── History modal ─────────────────────────────────────────
    //
    // Tabs: recents (storage history) and saved commands. The selected tab is
    // remembered for the browser session. Items can be copied, or inserted
    // into the last focused cell.

    var modalEl   = document.getElementById("dorm-modal");
    var modalBody = document.getElementById("dorm-modal-body");
    var TAB_KEY   = "dorm.historyTab";

    function storedTab() {
        try { return sessionStorage.getItem(TAB_KEY) || "recents"; } catch (e) { return "recents"; }
    }

    function setTab(name) {
        modalEl.querySelectorAll(".dorm-tab").forEach(function (tab) {
            var on = tab.dataset.tab === name;
            tab.classList.toggle("is-active", on);
            tab.setAttribute("aria-selected", on ? "true" : "false");
        });
        modalBody.querySelectorAll(".dorm-tab-panel").forEach(function (panel) {
            panel.hidden = panel.dataset.tab !== name;
        });
        try { sessionStorage.setItem(TAB_KEY, name); } catch (e) { /* storage unavailable */ }
    }

    // Server renders times in the project TIME_ZONE; show the viewer's local time.
    function localiseTimes(root) {
        root.querySelectorAll("time[datetime]").forEach(function (el) {
            var d = new Date(el.getAttribute("datetime"));
            if (isNaN(d)) return;
            el.textContent = d.toLocaleString(undefined, {
                month: "short", day: "numeric",
                hour: "2-digit", minute: "2-digit", second: "2-digit",
            });
            el.title = d.toString();
        });
    }

    function closeHistory() {
        modalEl.hidden = true;
        if (activeCell && cellsEl.contains(activeCell)) activeCell._cm.focus();
    }

    window.dormOpenHistory = function () {
        modalEl.hidden = false;
        setTab(storedTab());
        modalBody.innerHTML = '<p class="dorm-hist-empty">Loading…</p>';
        fetch(modalBody.dataset.url, { headers: { "X-Requested-With": "fetch" } })
            .then(function (resp) {
                if (!resp.ok) throw new Error("HTTP " + resp.status);
                return resp.text();
            })
            .then(function (html) {
                modalBody.innerHTML = html;
                localiseTimes(modalBody);
                setTab(storedTab());
            })
            .catch(function (err) {
                modalBody.innerHTML = '<p class="dorm-modal-error">Could not load history (' + err.message + ")</p>";
            });
    };

    function copyText(text) {
        // navigator.clipboard needs a secure context (fails on http://<lan-ip>)
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(text);
        }
        return new Promise(function (resolve, reject) {
            var ta = document.createElement("textarea");
            ta.value = text;
            ta.style.position = "fixed";
            ta.style.opacity  = "0";
            document.body.appendChild(ta);
            ta.select();
            var ok = document.execCommand("copy");
            ta.remove();
            ok ? resolve() : reject(new Error("copy failed"));
        });
    }

    function insertCode(code) {
        var cells  = allCells();
        var target = activeCell && cellsEl.contains(activeCell) ? activeCell : cells[cells.length - 1];
        closeHistory();
        target._cm.setValue(code);
        target._cm.focus();
        target._cm.setCursor(target._cm.lineCount(), 0);
    }

    modalEl.addEventListener("click", function (e) {
        if (e.target.closest("[data-close]")) return closeHistory();

        var tab = e.target.closest(".dorm-tab");
        if (tab) return setTab(tab.dataset.tab);

        var btn = e.target.closest("[data-hist-action]");
        if (!btn) return;
        var code = btn.closest(".dorm-hist-item").querySelector(".dorm-hist-code").textContent;
        if (btn.dataset.histAction === "insert") return insertCode(code);
        copyText(code)
            .then(function () { toast("Copied to clipboard"); })
            .catch(function () { toast("Could not copy", true); });
    });

    // ── Export modal ──────────────────────────────────────────

    var ROWS_PER_FILE = 1500;   // keep in sync with dorm/exports.py
    var exportModal   = document.getElementById("dorm-export-modal");
    var exportFormat  = null;
    var exporting     = false;

    function plural(n, word) {
        return n.toLocaleString() + " " + word + (n === 1 ? "" : "s");
    }

    function openExportChoice(format, table) {
        exportFormat = format;
        var loaded = table.querySelectorAll("tbody tr").length;
        var total  = parseInt(table.dataset.total, 10);
        var ext    = format.toUpperCase();

        exportModal.querySelector("[data-export-format]").textContent = ext;
        exportModal.querySelector("[data-export-visible]").textContent =
            "The " + plural(loaded, "row") + " shown, as a single " + ext + " file.";

        var full = "Re-runs the query and exports every row";
        if (!isNaN(total)) {
            full += " (" + plural(total, "row") + ")";
            full += total > ROWS_PER_FILE
                ? " as a .zip of " + Math.ceil(total / ROWS_PER_FILE) + " " + ext + " files, "
                  + ROWS_PER_FILE.toLocaleString() + " rows each."
                : " as a single " + ext + " file.";
        } else {
            full += ". Over " + ROWS_PER_FILE.toLocaleString() + " rows, files are split and zipped.";
        }
        exportModal.querySelector("[data-export-full]").textContent = full;
        exportModal.hidden = false;
        exportModal.querySelector("[data-choice=full]").focus();
    }

    function closeExportChoice() {
        exportModal.hidden = true;
    }

    function filenameFrom(resp, fallback) {
        var cd = resp.headers.get("Content-Disposition") || "";
        var m  = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(cd);
        return m ? decodeURIComponent(m[1]) : fallback;
    }

    function exportFull(format) {
        if (exporting || !lastFlow) return;
        exporting = true;

        var params = new URLSearchParams();
        lastFlow.forEach(function (code) { params.append("cells", code); });
        params.append("format", format);
        params.append("verbose", verboseCb && !verboseCb.checked ? "0" : "1");

        toast("Re-running query for the full export…");
        post(cellsEl.dataset.exportUrl, params)
            .then(function (resp) {
                if (!resp.ok) {
                    return resp.json().then(function (d) { throw new Error(d.error || "HTTP " + resp.status); },
                                            function () { throw new Error("HTTP " + resp.status); });
                }
                return resp.blob().then(function (blob) {
                    var name = filenameFrom(resp, "dorm_records." + format);
                    downloadBlob(blob, name);
                    toast("Downloaded " + name);
                });
            })
            .catch(function (err) { toast("Export failed: " + err.message, true); })
            .then(function () { exporting = false; });
    }

    exportModal.addEventListener("click", function (e) {
        if (e.target.closest("[data-close]")) return closeExportChoice();
        var choice = e.target.closest("[data-choice]");
        if (!choice) return;
        closeExportChoice();
        if (choice.dataset.choice === "full") exportFull(exportFormat);
        else exportLoaded(exportFormat, document.querySelector(".dorm-table"));
    });

    document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape") return;
        if (!exportModal.hidden) closeExportChoice();
        else if (!modalEl.hidden) closeHistory();
    });

}());
