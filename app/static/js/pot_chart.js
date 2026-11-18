// Pot balance over time, drawn as inline SVG: one small chart per pot with the pot
// balance against what its cards owe, plus a marker for every move the sync made.
// Reads its data from <script type="application/json" id="..."> and renders into
// elements carrying data-pot-chart="<that id>".
(function () {
    "use strict";

    var SVG_NS = "http://www.w3.org/2000/svg";
    var HEIGHT = 200;
    var MARGIN = { top: 12, right: 12, bottom: 26, left: 60 };

    function pounds(pence) {
        if (pence === null || pence === undefined) return "–";
        var sign = pence < 0 ? "-" : "";
        return sign + "£" + (Math.abs(pence) / 100).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function shortPounds(pence) {
        var value = pence / 100;
        if (Math.abs(value) >= 1000) return "£" + (value / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 }) + "k";
        return "£" + value.toLocaleString("en-GB", { maximumFractionDigits: 0 });
    }

    function formatTime(t, withTime) {
        var d = new Date(t * 1000);
        var options = { day: "numeric", month: "short" };
        if (withTime) { options.hour = "2-digit"; options.minute = "2-digit"; }
        return d.toLocaleString([], options);
    }

    function el(name, attrs, parent) {
        var node = document.createElementNS(SVG_NS, name);
        Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
        if (parent) parent.appendChild(node);
        return node;
    }

    function html(tag, className, text, parent) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        if (parent) parent.appendChild(node);
        return node;
    }

    // A "nice" step (1, 2, 2.5 or 5 x 10^n) giving roughly `count` ticks up to max.
    function niceTicks(max, count) {
        if (max <= 0) return [0, 100];
        var raw = max / count;
        var magnitude = Math.pow(10, Math.floor(Math.log10(raw)));
        var step = [1, 2, 2.5, 5, 10].map(function (m) { return m * magnitude; }).find(function (s) { return s >= raw; });
        var ticks = [];
        for (var v = 0; v <= max + step * 0.001; v += step) ticks.push(v);
        if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step);
        return ticks;
    }

    // Value of a step series at time t: the latest point at or before t.
    function valueAt(points, key, t) {
        var value = null;
        for (var i = 0; i < points.length && points[i].t <= t; i++) value = points[i][key];
        return value;
    }

    function stepPath(points, key, x, y, end) {
        var d = "";
        var drawing = false;
        var last = null;
        points.forEach(function (p, i) {
            var v = p[key];
            var px = x(p.t);
            if (v === null || v === undefined) {
                if (drawing) d += "H" + px;  // the line runs up to the gap
                drawing = false; last = null; return;
            }
            var py = y(v);
            if (!drawing) { d += "M" + px + "," + py; drawing = true; }
            else { d += "H" + px + "V" + py; }
            last = v;
            if (i === points.length - 1 && last !== null) d += "H" + x(end);
        });
        return d;
    }

    function renderPot(container, pot, data, tooltip) {
        var width = Math.max(container.clientWidth, 280);
        var innerW = width - MARGIN.left - MARGIN.right;
        var innerH = HEIGHT - MARGIN.top - MARGIN.bottom;
        var t0 = data.since, t1 = data.now;
        var points = pot.points;
        var moves = data.moves.filter(function (m) { return m.pot_id === pot.pot_id; });

        var max = 0;
        points.forEach(function (p) { max = Math.max(max, p.pot || 0, p.card || 0); });
        moves.forEach(function (m) { if (m.pot_after !== null) max = Math.max(max, m.pot_after); });
        var ticks = niceTicks(max, 4);
        var yMax = ticks[ticks.length - 1];

        var x = function (t) { return MARGIN.left + ((t - t0) / (t1 - t0)) * innerW; };
        var y = function (v) { return MARGIN.top + innerH - (v / yMax) * innerH; };

        var svg = el("svg", {
            viewBox: "0 0 " + width + " " + HEIGHT, width: width, height: HEIGHT,
            role: "img", "aria-label": pot.pot_name + " balance over time", class: "pot-chart-svg",
        });

        // Grid and y axis labels.
        ticks.forEach(function (v) {
            el("line", { x1: MARGIN.left, x2: width - MARGIN.right, y1: y(v), y2: y(v), class: v === 0 ? "pc-baseline" : "pc-grid" }, svg);
            var label = el("text", { x: MARGIN.left - 8, y: y(v), dy: "0.32em", "text-anchor": "end", class: "pc-axis" }, svg);
            label.textContent = shortPounds(v);
        });

        // X axis: about one label per 120px.
        var xCount = Math.max(2, Math.floor(innerW / 120));
        for (var i = 0; i <= xCount; i++) {
            var t = t0 + ((t1 - t0) * i) / xCount;
            var label = el("text", {
                x: x(t), y: HEIGHT - 6, class: "pc-axis",
                "text-anchor": i === 0 ? "start" : i === xCount ? "end" : "middle",
            }, svg);
            label.textContent = formatTime(t, t1 - t0 <= 2 * 86400);
        }

        el("path", { d: stepPath(points, "card", x, y, t1), class: "pc-card" }, svg);
        el("path", { d: stepPath(points, "pot", x, y, t1), class: "pc-pot" }, svg);

        moves.forEach(function (m) {
            if (m.pot_after === null) return;
            el("circle", { cx: x(m.t), cy: y(m.pot_after), r: 4, class: m.amount >= 0 ? "pc-move pc-deposit" : "pc-move pc-withdraw" }, svg);
        });

        var crosshair = el("line", { y1: MARGIN.top, y2: MARGIN.top + innerH, class: "pc-crosshair", visibility: "hidden" }, svg);
        var focusPot = el("circle", { r: 4, class: "pc-focus pc-focus-pot", visibility: "hidden" }, svg);
        var focusCard = el("circle", { r: 4, class: "pc-focus pc-focus-card", visibility: "hidden" }, svg);

        // Snap targets: every recorded point and every move.
        var stops = points.map(function (p) { return { t: p.t }; })
            .concat(moves.map(function (m) { return { t: m.t, move: m }; }))
            .concat([{ t: t1 }])
            .sort(function (a, b) { return a.t - b.t; });

        function hide() {
            [crosshair, focusPot, focusCard].forEach(function (n) { n.setAttribute("visibility", "hidden"); });
            tooltip.hidden = true;
        }

        function show(clientX) {
            var rect = svg.getBoundingClientRect();
            var px = (clientX - rect.left) * (width / rect.width);
            var t = t0 + ((px - MARGIN.left) / innerW) * (t1 - t0);
            var best = stops[0], bestDist = Infinity;
            stops.forEach(function (s) {
                var dist = Math.abs(s.t - t);
                if (dist < bestDist) { best = s; bestDist = dist; }
            });
            var potValue = best.move && best.move.pot_after !== null ? best.move.pot_after : valueAt(points, "pot", best.t);
            var cardValue = valueAt(points, "card", best.t);
            if (potValue === null && cardValue === null) { hide(); return; }
            var cx = x(best.t);
            crosshair.setAttribute("x1", cx); crosshair.setAttribute("x2", cx);
            crosshair.setAttribute("visibility", "visible");
            [[focusPot, potValue], [focusCard, cardValue]].forEach(function (pair) {
                if (pair[1] === null) { pair[0].setAttribute("visibility", "hidden"); return; }
                pair[0].setAttribute("cx", cx); pair[0].setAttribute("cy", y(pair[1]));
                pair[0].setAttribute("visibility", "visible");
            });

            tooltip.replaceChildren();
            html("div", "pc-tip-time", best.t === t1 ? "Now" : formatTime(best.t, true), tooltip);
            [["pc-key-pot", potValue, "Pot balance"], ["pc-key-card", cardValue, "Cards owe"]].forEach(function (row) {
                var line = html("div", "pc-tip-row", null, tooltip);
                html("span", "pc-key " + row[0], null, line);
                html("strong", null, pounds(row[1]), line);
                html("span", "pc-tip-label", row[2], line);
            });
            if (potValue !== null && cardValue !== null) {
                var diff = potValue - cardValue;
                html("div", "pc-tip-note", diff === 0 ? "In sync" : diff > 0 ? "Pot over by " + pounds(diff) : "Pot short by " + pounds(-diff), tooltip);
            }
            if (best.move) {
                var m = best.move;
                html("div", "pc-tip-move", (m.amount >= 0 ? "Deposited " : "Withdrew ") + pounds(Math.abs(m.amount)) + " · " + m.reason + " (" + m.card + ")", tooltip);
            }
            tooltip.hidden = false;
            var box = container.getBoundingClientRect();
            var left = (cx / width) * rect.width + (rect.left - box.left);
            var tipW = tooltip.offsetWidth;
            tooltip.style.left = Math.min(Math.max(left - tipW / 2, 0), box.width - tipW) + "px";
        }

        svg.addEventListener("pointermove", function (e) { show(e.clientX); });
        svg.addEventListener("pointerdown", function (e) { show(e.clientX); });
        svg.addEventListener("pointerleave", hide);
        return svg;
    }

    function renderAll(root, data) {
        root.replaceChildren();
        if (!data.pots.length) {
            html("p", "pc-empty", "Balance history appears here after the next sync.", root);
            return;
        }
        data.pots.forEach(function (pot) {
            var card = html("figure", "pc-figure", null, root);
            var head = html("figcaption", "pc-head", null, card);
            html("span", "pc-title", pot.pot_name, head);
            var legend = html("span", "pc-legend", null, head);
            [["pc-key-pot", "Pot balance"], ["pc-key-card", "Cards owe"], ["pc-key-move", "Move"]].forEach(function (item) {
                var entry = html("span", "pc-legend-item", null, legend);
                html("span", "pc-key " + item[0], null, entry);
                html("span", null, item[1], entry);
            });
            var plot = html("div", "pc-plot", null, card);
            var tooltip = html("div", "pc-tooltip", null, plot);
            tooltip.hidden = true;
            tooltip.setAttribute("role", "status");
            plot.insertBefore(renderPot(plot, pot, data, tooltip), tooltip);
        });
    }

    document.querySelectorAll("[data-pot-chart]").forEach(function (root) {
        var source = document.getElementById(root.dataset.potChart);
        if (!source) return;
        var data;
        try { data = JSON.parse(source.textContent); } catch (e) { return; }
        renderAll(root, data);
        var lastWidth = root.clientWidth;
        if (window.ResizeObserver) {
            new ResizeObserver(function () {
                if (Math.abs(root.clientWidth - lastWidth) < 8) return;
                lastWidth = root.clientWidth;
                renderAll(root, data);
            }).observe(root);
        }
    });
})();
