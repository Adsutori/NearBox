// ── INICJALIZACJA MAPY ──
const map = L.map('map').setView([52.0, 19.0], 6);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a>'
}).addTo(map);

let markersLayer = L.layerGroup().addTo(map);
let aiSelectedMarker = null;

// ══════════════════════════════════════════
//  ANIMACJE
// ══════════════════════════════════════════

// ── LOADING MODAL ──
function showLoading(text = "Ładowanie punktów...") {
    document.getElementById("loading-text").textContent = text;
    document.getElementById("loading-modal").classList.add("active");
}

function hideLoading() {
    document.getElementById("loading-modal").classList.remove("active");
}


// ── AI THINKING — dymek z kropkami ──
function showAIThinking() {
    const box = document.getElementById("ai-response");
    box.className = "thinking";
    box.innerHTML = `
        <span class="thinking-label">AI myśli...</span>
        <div class="typing-bubble">
            <span></span><span></span><span></span>
        </div>`;
    box.style.display = "flex";
}

function hideAIThinking(text) {
    const box = document.getElementById("ai-response");
    box.className = "";
    box.style.display = "block";
    box.textContent = text;

    highlightAIMarker(text);
}

function highlightAIMarker(aiText) {
    // Bardziej agresywny regex — łapie GRM08M, POP-GRO4, WAW01A itp.
    const match = aiText.match(/\b([A-Z]{2,6}(?:-[A-Z]{1,4})?\d{1,3}[A-Z]{0,2})\b/);

    console.log("[AI HIGHLIGHT] szukam w tekście:", aiText);
    console.log("[AI HIGHLIGHT] znaleziony kod:", match ? match[1] : "BRAK");

    if (!match) return;

    const targetName = match[1];

    // Resetuj poprzednio wybrany marker
    if (aiSelectedMarker) {
        aiSelectedMarker.setIcon(createInpostIcon(aiSelectedMarker.options._status, false));
        aiSelectedMarker = null;
    }

    // Debug — wypisz wszystkie nazwy markerów na mapie
    const allNames = [];
    markersLayer.eachLayer(m => allNames.push(m.options._name));
    console.log("[AI HIGHLIGHT] markery na mapie:", allNames);

    // Znajdź marker po nazwie i podświetl go
    markersLayer.eachLayer(marker => {
        if (marker.options._name === targetName) {
            marker.setIcon(createInpostIcon(marker.options._status, true));
            aiSelectedMarker = marker;
            map.setView(marker.getLatLng(), 16, { animate: true });
            marker.openPopup();
            console.log("[AI HIGHLIGHT] ✅ podświetlono:", targetName);
        }
    });
}



// ══════════════════════════════════════════
//  IKONA INPOST
// ══════════════════════════════════════════

function createInpostIcon(status, isAiSelected = false) {
    const borderColor = isAiSelected  ? "#22c55e"
                      : status === "Operating" ? "#ffd402"
                      : status === "Disabled"  ? "#e74c3c"
                      :                          "#95a5a6";

    const animClass = isAiSelected ? "ai-selected-marker" : "";

    return L.divIcon({
        html: `
            <div class="${animClass}" style="
                width:36px; height:36px;
                border-radius:50%;
                border:3px solid ${borderColor};
                background:#ffd402;
                display:flex; align-items:center; justify-content:center;
                box-shadow:0 2px 6px rgba(0,0,0,0.3);
                overflow:hidden;
            ">
                <img src="${INPOST_LOGO_URL}"
                     style="width:26px;height:26px;object-fit:contain;">
            </div>`,
        className:   "",
        iconSize:    [36, 36],
        iconAnchor:  [18, 18],
        popupAnchor: [0, -22]
    });
}



// ══════════════════════════════════════════
//  POPUP
// ══════════════════════════════════════════

function buildPopup(point) {
    const badgeClass = point.status === "Operating" ? "badge-operating"
                     : point.status === "Disabled"  ? "badge-disabled"
                     :                                "badge-other";

    const statusLabel = point.status === "Operating" ? "✅ Działa"
                      : point.status === "Disabled"  ? "❌ Wyłączony"
                      :                                `⚠️ ${point.status}`;

    const imageHtml = point.image_url
        ? `<img class="popup-image" src="${point.image_url}"
                alt="${point.name}" onerror="this.style.display='none'">`
        : "";

    const descHtml = point.location_description
        ? `<div class="popup-row">📍 ${point.location_description}</div>`
        : "";

    return `
        <div class="popup-wrapper">
            ${imageHtml}
            <div class="popup-name">${point.name}</div>
            <div class="popup-address">${point.address || ""}, ${point.city || ""}</div>
            <div class="popup-row">
                <span class="badge ${badgeClass}">${statusLabel}</span>
            </div>
            <div class="popup-row">🕐 ${point.opening_hours || "Brak danych"}</div>
            ${descHtml}
        </div>`;
}


// ══════════════════════════════════════════
//  FILTRY
// ══════════════════════════════════════════

function getFilters() {
    return {
        only_locker:      document.getElementById("filter-locker").checked,
        only_247:         document.getElementById("filter-247").checked,
        only_operating:   document.getElementById("filter-operating").checked,
        only_outdoor:     document.getElementById("filter-outdoor").checked,
        only_easy_access: document.getElementById("filter-easy-access").checked,
    };
}


// ══════════════════════════════════════════
//  FETCH PUNKTÓW
// ══════════════════════════════════════════

async function fetchPoints() {
    const city   = document.getElementById("city-input").value.trim();
    const status = document.getElementById("status");

    if (!city) {
        status.textContent = "⚠️ Wpisz nazwę miasta";
        return;
    }

    status.textContent = "";
    markersLayer.clearLayers();
    showLoading("Szukam paczkomatów...");

    try {
        const filters = getFilters();
        const params  = new URLSearchParams({ city, ...filters });
        const res     = await fetch(`/api/points/?${params}`);

        hideLoading();

        if (!res.ok) {
            status.textContent = "❌ Błąd serwera";
            return;
        }

        const data = await res.json();

        if (data.length === 0) {
            status.textContent = "🔍 Brak wyników (zmień filtry)";
            return;
        }

        const bounds = [];
        data.forEach(point => {
            if (!point.lat || !point.lng) return;

            const marker = L.marker([point.lat, point.lng], {
                icon: createInpostIcon(point.status),
                _name:   point.name,
                _status: point.status
            });

            marker.bindPopup(buildPopup(point), {
                maxWidth: 240,
                className: "inpost-popup"
            });

            markersLayer.addLayer(marker);
            bounds.push([point.lat, point.lng]);
        });

        if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [40, 40] });
        }

        status.textContent = `✅ Znaleziono ${data.length} punktów`;

    } catch (err) {
        hideLoading();``
        console.error(err);
        status.textContent = "❌ Błąd połączenia";
    }
}


// ══════════════════════════════════════════
//  MOJA LOKALIZACJA
// ══════════════════════════════════════════

function useMyLocation() {
    const status = document.getElementById("status");

    showLoading("Szukam Twojej lokalizacji...");

    navigator.geolocation.getCurrentPosition(
        async (pos) => {
            const { latitude, longitude } = pos.coords;

            map.setView([latitude, longitude], 13);

            L.marker([latitude, longitude], {
                icon: L.divIcon({
                    html: `<div style="
                        width:16px; height:16px;
                        background:#4285f4;
                        border:3px solid white;
                        border-radius:50%;
                        box-shadow:0 2px 6px rgba(0,0,0,0.4);
                    "></div>`,
                    className:  "",
                    iconSize:   [16, 16],
                    iconAnchor: [8, 8]
                })
            }).addTo(map).bindPopup("📍 Twoja lokalizacja");

            try {
                const res  = await fetch(`/api/points/?lat=${latitude}&lng=${longitude}`);
                const data = await res.json();

                hideLoading();

                // renderMarkers zamiast fetchPoints — dane już mamy
                const bounds = [];
                data.forEach(point => {
                    if (!point.lat || !point.lng) return;

                    const marker = L.marker([point.lat, point.lng], {
                        icon: createInpostIcon(point.status),
                        _name:   point.name,
                        _status: point.status
                    });

                    marker.bindPopup(buildPopup(point), {
                        maxWidth: 240,
                        className: "inpost-popup"
                    });

                    markersLayer.addLayer(marker);
                    bounds.push([point.lat, point.lng]);
                });

                if (bounds.length > 0) {
                    map.fitBounds(bounds, { padding: [40, 40] });
                }

                status.textContent = `✅ Znaleziono ${data.length} punktów w pobliżu`;

            } catch (err) {
                hideLoading();
                console.error(err);
                status.textContent = "❌ Błąd połączenia";
            }
        },
        () => {
            hideLoading();
            status.textContent = "❌ Brak dostępu do lokalizacji";
        }
    );
}


// ══════════════════════════════════════════
//  AI
// ══════════════════════════════════════════

async function askAI() {
    const query     = document.getElementById("ai-input").value.trim();
    const cityInput = document.getElementById("city-input").value.trim();

    if (!query) return;

    if (!cityInput) {
        hideAIThinking("⚠️ Najpierw wyszukaj miasto.");
        return;
    }

    showAIThinking();

    try {
        const res = await fetch("/api/ai/", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ query, city: cityInput })
        });

        const data = await res.json();
        console.log("[AI DEBUG] odpowiedź:", data); 
        hideAIThinking(data.recommendation || "Brak odpowiedzi.");

    } catch (err) {
        hideAIThinking("❌ Błąd połączenia z AI.");
    }
}


// ══════════════════════════════════════════
//  ENTER + INIT
// ══════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("city-input").addEventListener("keydown", e => {
        if (e.key === "Enter") fetchPoints();
    });

    document.getElementById("ai-input").addEventListener("keydown", e => {
        if (e.key === "Enter") askAI();
    });
});
