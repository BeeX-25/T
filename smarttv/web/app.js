/* Phone remote: talks to the same JSON API the CLI uses. */
(function () {
  "use strict";

  var TOKEN_KEY = "smarttv.token";
  var token = "";
  try { token = localStorage.getItem(TOKEN_KEY) || ""; } catch (e) { token = ""; }

  var el = function (id) { return document.getElementById(id); };
  var toastTimer = null;

  function toast(message, isError) {
    var node = el("toast");
    node.textContent = message;
    node.className = "toast show" + (isError ? " error" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { node.className = "toast"; }, 2600);
  }

  function api(method, path, body) {
    var headers = { "Content-Type": "application/json" };
    if (token) headers["X-Auth-Token"] = token;
    return fetch(path, {
      method: method,
      headers: headers,
      body: body ? JSON.stringify(body) : undefined
    }).then(function (response) {
      return response.json().catch(function () {
        throw new Error("رد غير مفهوم من الخادم");
      }).then(function (payload) {
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.error || ("HTTP " + response.status));
        }
        return payload.data;
      });
    });
  }

  function send(method, path, body, okMessage) {
    return api(method, path, body).then(function (data) {
      if (okMessage) toast(okMessage);
      refresh();
      return data;
    }).catch(function (error) {
      toast(error.message, true);
    });
  }

  /* --- rendering ---------------------------------------------------- */

  function formatClock(seconds) {
    if (seconds === null || seconds === undefined) return "";
    seconds = Math.max(0, Math.round(seconds));
    var m = Math.floor(seconds / 60), s = seconds % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function renderStatus(data) {
    var dot = el("dot");
    var text = el("statusText");
    var power = data.power;
    dot.className = "dot" + (power === "on" ? " on" : power === "standby" ? " off" : "");
    var parts = [];
    parts.push(data.backend ? ("الاتصال: " + data.backend) : "لا يوجد اتصال بالتلفاز");
    if (power === "on") parts.push("التلفاز يعمل");
    else if (power === "standby") parts.push("التلفاز في وضع الاستعداد");
    else if (data.power_error) parts.push("تعذّرت قراءة الحالة");
    text.textContent = parts.join(" · ");

    var player = data.player || {};
    var now = el("nowPlaying");
    if (player.running) {
      var label = player.title || "قيد التشغيل";
      var clock = player.position != null && player.duration
        ? " (" + formatClock(player.position) + " / " + formatClock(player.duration) + ")"
        : "";
      now.textContent = (player.paused ? "⏸ " : "▶ ") + label + clock;
    } else {
      now.textContent = player.available ? "" : "المشغّل غير مثبّت (ثبّت mpv لتشغيل الروابط)";
    }

    var sleep = (data.scheduler || {}).sleep_timer_seconds;
    el("sleepInfo").textContent = sleep
      ? "سينطفئ التلفاز بعد " + Math.ceil(sleep / 60) + " دقيقة"
      : "";
  }

  function renderConfig(data) {
    var box = el("shortcuts");
    box.innerHTML = "";
    (data.shortcuts || []).forEach(function (item) {
      var chip = document.createElement("button");
      chip.className = "chip";
      chip.type = "button";
      chip.textContent = item.name;
      chip.addEventListener("click", function () {
        send("POST", "/api/cast", { url: item.url }, "جارٍ تشغيل " + item.name);
      });
      box.appendChild(chip);
    });

    var sources = el("sources");
    sources.innerHTML = "";
    for (var index = 1; index <= 4; index++) {
      (function (i) {
        var chip = document.createElement("button");
        chip.className = "chip";
        chip.type = "button";
        chip.textContent = "HDMI " + i;
        chip.addEventListener("click", function () {
          send("POST", "/api/source", { index: i }, "تحويل إلى HDMI " + i);
        });
        sources.appendChild(chip);
      })(index);
    }

    el("backendInfo").textContent = (data.backends || [])
      .map(function (b) { return b.name + (b.available ? " ✓" : " ✗"); })
      .join(" · ") || "لا توجد واجهات مفعّلة";
  }

  /* --- actions ------------------------------------------------------- */

  var handlers = {
    power: function (node) {
      send("POST", "/api/power", { state: node.dataset.state || "toggle" });
    },
    key: function (node) {
      send("POST", "/api/key", { key: node.dataset.key });
    },
    volume: function (node) {
      send("POST", "/api/volume", { action: node.dataset.value });
    },
    player: function (node) {
      var body = { action: node.dataset.value };
      if (node.dataset.amount) body.value = Number(node.dataset.amount);
      send("POST", "/api/player", body);
    },
    sleep: function (node) {
      send("POST", "/api/sleep", { minutes: Number(node.dataset.minutes) },
        "مؤقت النوم: " + node.dataset.minutes + " دقيقة");
    },
    "sleep-cancel": function () {
      send("DELETE", "/api/sleep", null, "أُلغي مؤقت النوم");
    }
  };

  document.addEventListener("click", function (event) {
    var node = event.target.closest("[data-action]");
    if (!node) return;
    var handler = handlers[node.dataset.action];
    if (!handler) return;
    event.preventDefault();
    if (navigator.vibrate) navigator.vibrate(8);
    handler(node);
  });

  el("castForm").addEventListener("submit", function (event) {
    event.preventDefault();
    var input = el("castUrl");
    if (!input.value) return;
    send("POST", "/api/cast", { url: input.value }, "جارٍ التشغيل على التلفاز");
    input.blur();
  });

  el("settingsBtn").addEventListener("click", function () {
    el("tokenInput").value = token;
    el("settings").showModal();
  });

  el("settings").addEventListener("close", function () {
    if (el("settings").returnValue !== "save") return;
    token = el("tokenInput").value.trim();
    try { localStorage.setItem(TOKEN_KEY, token); } catch (e) { /* private mode */ }
    boot();
  });

  el("discoverBtn").addEventListener("click", function () {
    toast("جارٍ البحث في الشبكة…");
    api("GET", "/api/discover").then(function (data) {
      var found = (data.devices || []).map(function (device) {
        return (device.name || device.server || "جهاز") + " - " + device.host;
      });
      toast(found.length ? found.join(" | ") : "لم يُعثر على أجهزة");
    }).catch(function (error) { toast(error.message, true); });
  });

  /* keyboard control from a laptop */
  var KEYBOARD = {
    ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right",
    Enter: "select", Backspace: "back", Escape: "exit", h: "home", i: "info"
  };
  document.addEventListener("keydown", function (event) {
    if (event.target.matches("input, textarea")) return;
    var key = KEYBOARD[event.key];
    if (key) {
      event.preventDefault();
      send("POST", "/api/key", { key: key });
    } else if (event.key === "+" || event.key === "=") {
      send("POST", "/api/volume", { action: "up" });
    } else if (event.key === "-") {
      send("POST", "/api/volume", { action: "down" });
    } else if (event.key === " ") {
      event.preventDefault();
      send("POST", "/api/player", { action: "toggle" });
    }
  });

  /* --- polling ------------------------------------------------------- */

  var refreshing = false;
  function refresh() {
    if (refreshing) return;
    refreshing = true;
    api("GET", "/api/status")
      .then(renderStatus)
      .catch(function (error) {
        el("statusText").textContent = error.message;
        el("dot").className = "dot off";
      })
      .then(function () { refreshing = false; });
  }

  function boot() {
    api("GET", "/api/config").then(renderConfig).catch(function (error) {
      toast(error.message, true);
    });
    refresh();
  }

  boot();
  setInterval(function () {
    if (!document.hidden) refresh();
  }, 4000);
})();
