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
      var label = (data.now_playing && data.now_playing.name) || player.title || "قيد التشغيل";
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


  /* --- library ------------------------------------------------------- */

  var library = { kind: "live", query: "", group: "", offset: 0, limit: 60, busy: false };

  function play(item) {
    send("POST", "/api/cast", {
      url: item.url, name: item.name, kind: item.kind || library.kind,
      logo: item.logo || "", group: item.group || ""
    }, "جارٍ التشغيل: " + (item.name || ""));
  }

  function initials(name) {
    // "الجزيرة" starts with the article, so two raw letters say nothing;
    // drop it before taking the badge letters.
    var text = (name || "?").trim();
    if (text.length > 3 && text.slice(0, 2) === "ال") text = text.slice(2);
    return text.slice(0, 2);
  }

  function itemCard(item, extra, onClick) {
    var card = document.createElement("button");
    card.className = "item";
    card.type = "button";

    var thumb = document.createElement("div");
    thumb.className = "thumb";
    if (item.logo) {
      var image = document.createElement("img");
      image.loading = "lazy";
      image.alt = "";
      image.src = item.logo;
      // A dead logo URL must not leave an empty hole in the grid.
      image.addEventListener("error", function () {
        thumb.textContent = initials(item.name);
      });
      thumb.appendChild(image);
    } else {
      thumb.textContent = initials(item.name);
    }
    card.appendChild(thumb);

    var title = document.createElement("div");
    title.className = "title";
    title.textContent = item.name || item.url;
    card.appendChild(title);

    if (extra) {
      var sub = document.createElement("div");
      sub.className = "sub";
      sub.textContent = extra;
      card.appendChild(sub);
    }

    if (item.duration && item.position) {
      var bar = document.createElement("div");
      bar.className = "bar";
      var fill = document.createElement("i");
      fill.style.width = Math.min(100, (item.position / item.duration) * 100) + "%";
      bar.appendChild(fill);
      card.appendChild(bar);
    }

    if (item.url && library.kind !== "series") {
      var star = document.createElement("button");
      star.className = "star";
      star.type = "button";
      star.textContent = item.favorite ? "★" : "☆";
      star.addEventListener("click", function (event) {
        event.stopPropagation();
        api("POST", "/api/favorites", item).then(function (data) {
          star.textContent = data.favorite ? "★" : "☆";
          item.favorite = data.favorite;
        }).catch(function (error) { toast(error.message, true); });
      });
      card.appendChild(star);
    }

    card.addEventListener("click", onClick || function () { play(item); });
    return card;
  }

  function showEpisodes(show) {
    el("episodesTitle").textContent = show.name;
    var list = el("episodesList");
    list.innerHTML = "";
    show.episodes.forEach(function (episode) {
      var button = document.createElement("button");
      button.type = "button";
      var label = episode.season && episode.episode
        ? "الموسم " + episode.season + " · الحلقة " + episode.episode
        : episode.name;
      button.textContent = label;
      button.addEventListener("click", function () {
        el("episodes").close();
        play({ url: episode.url, name: show.name + " - " + label, kind: "series" });
      });
      list.appendChild(button);
    });
    el("episodes").showModal();
  }

  function renderGroups(groups) {
    var box = el("groups");
    box.innerHTML = "";
    if (!groups || !groups.length) return;
    groups.slice(0, 14).forEach(function (group) {
      var chip = document.createElement("button");
      chip.className = "chip" + (library.group === group.name ? " is-on" : "");
      chip.type = "button";
      chip.textContent = group.name + " (" + group.count + ")";
      chip.addEventListener("click", function () {
        library.group = library.group === group.name ? "" : group.name;
        loadLibrary(true);
      });
      box.appendChild(chip);
    });
  }

  function query(params) {
    return Object.keys(params)
      .filter(function (key) { return params[key] !== "" && params[key] != null; })
      .map(function (key) { return key + "=" + encodeURIComponent(params[key]); })
      .join("&");
  }

  function loadLibrary(reset) {
    if (library.busy) return;
    if (reset) { library.offset = 0; el("results").innerHTML = ""; }
    library.busy = true;
    var info = el("libraryInfo");
    info.textContent = "جارٍ التحميل…";

    var request;
    if (library.kind === "favorites") {
      request = api("GET", "/api/favorites").then(function (data) {
        return { items: data.items, total: data.items.length };
      });
    } else if (library.kind === "resume") {
      request = api("GET", "/api/resume").then(function (data) {
        var seen = {};
        var items = data.items.concat(data.history).filter(function (entry) {
          if (!entry.url || seen[entry.url]) return false;
          seen[entry.url] = true;
          return true;
        });
        return { items: items, total: items.length };
      });
    } else if (library.kind === "series") {
      request = api("GET", "/api/series?" + query({
        q: library.query, limit: library.limit, offset: library.offset
      }));
    } else {
      request = api("GET", "/api/catalog?" + query({
        kind: library.kind, q: library.query, group: library.group,
        limit: library.limit, offset: library.offset
      }));
    }

    request.then(function (data) {
      renderGroups(data.groups);
      var results = el("results");
      (data.items || []).forEach(function (item) {
        var extra = "";
        if (library.kind === "series") extra = (item.episode_count || 0) + " حلقة";
        else if (item.group) extra = item.group;
        // A show has no stream of its own - it opens its episode list.
        var card = library.kind === "series"
          ? itemCard(item, extra, function () { showEpisodes(item); })
          : itemCard(item, extra);
        results.appendChild(card);
      });
      library.offset += (data.items || []).length;
      var more = el("moreBtn");
      more.hidden = !(data.total && library.offset < data.total);
      if (!results.children.length) {
        info.textContent = (data.status && data.status.sources === 0)
          ? "لا توجد مصادر بعد — أضف قوائم M3U في ملف الإعدادات (catalog.sources)"
          : "لا نتائج";
      } else {
        info.textContent = "عرض " + library.offset + " من " + (data.total || library.offset);
      }
      if (data.status && data.status.errors && data.status.errors.length) {
        info.textContent += " · تعذّر تحميل " + data.status.errors.length + " مصدر";
      }
    }).catch(function (error) {
      info.textContent = error.message;
    }).then(function () { library.busy = false; });
  }

  el("tabs").addEventListener("click", function (event) {
    var tab = event.target.closest(".tab");
    if (!tab) return;
    Array.prototype.forEach.call(el("tabs").children, function (node) {
      node.classList.toggle("is-active", node === tab);
    });
    library.kind = tab.dataset.kind;
    library.group = "";
    el("groups").innerHTML = "";
    loadLibrary(true);
  });

  var searchTimer = null;
  el("searchInput").addEventListener("input", function (event) {
    clearTimeout(searchTimer);
    var value = event.target.value;
    searchTimer = setTimeout(function () {
      library.query = value;
      loadLibrary(true);
    }, 350);
  });

  el("searchForm").addEventListener("submit", function (event) { event.preventDefault(); });
  el("moreBtn").addEventListener("click", function () { loadLibrary(false); });
  el("episodesClose").addEventListener("click", function () { el("episodes").close(); });
  el("refreshBtn").addEventListener("click", function () {
    toast("جارٍ تحديث القوائم…");
    api("POST", "/api/catalog/refresh").then(function (data) {
      toast("تم تحميل " + data.items + " عنصراً");
      loadLibrary(true);
    }).catch(function (error) { toast(error.message, true); });
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
    loadLibrary(true);
  }

  boot();
  setInterval(function () {
    if (!document.hidden) refresh();
  }, 4000);
})();
