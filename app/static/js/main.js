// ══════════════════════════════════════════
//  THEME — init przed mapą
// ══════════════════════════════════════════

const currentTheme = localStorage.getItem('theme') || 'dark';
document.documentElement.setAttribute('data-theme', currentTheme);

// ── INICJALIZACJA MAPY ──
const map = L.map('map').setView([52.0, 19.0], 6);

const tileDark = L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    {
        attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> © <a href="https://carto.com">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }
);

const tileLight = L.tileLayer(
    'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    {
        attribution: '© <a href="https://openstreetmap.org">OpenStreetMap</a> © <a href="https://carto.com">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 19
    }
);

// Dodaj właściwy tile layer od razu
if (currentTheme === 'light') {
    tileLight.addTo(map);
} else {
    tileDark.addTo(map);
}

let markersLayer     = L.layerGroup().addTo(map);
let aiSelectedMarker = null;


// ══════════════════════════════════════════
//  THEME TOGGLE
// ══════════════════════════════════════════

function toggleTheme() {
    const html    = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next    = current === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);

    if (next === 'light') {
        tileDark.remove();
        tileLight.addTo(map);
    } else {
        tileLight.remove();
        tileDark.addTo(map);
    }

    map.invalidateSize();
}

// Podpięcie przycisku — po załadowaniu DOM
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

    document.getElementById('city-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') fetchPoints();
    });
    document.getElementById('ai-input').addEventListener('keydown', e => {
        if (e.key === 'Enter') askAI();
    });
});


// ══════════════════════════════════════════
//  LOADING MODAL
// ══════════════════════════════════════════

function showLoading(text = "Ładowanie punktów…") {
    document.getElementById("loading-text").textContent = text;
    document.getElementById("loading-modal").classList.add("active");
}

function hideLoading() {
    document.getElementById("loading-modal").classList.remove("active");
}


// ══════════════════════════════════════════
//  AI THINKING
// ══════════════════════════════════════════

function showAIThinking() {
    const box = document.getElementById("ai-response");
    box.className = "thinking";
    box.innerHTML = `
        <span class="thinking-label">AI myśli…</span>
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


// ══════════════════════════════════════════
//  AI HIGHLIGHT MARKER
// ══════════════════════════════════════════

function highlightAIMarker(aiText) {
    const match = aiText.match(/\b([A-Z]{2,6}(?:-[A-Z]{1,4})?\d{1,3}[A-Z]{0,2})\b/);

    console.log("[AI HIGHLIGHT] kod:", match ? match[1] : "BRAK");
    if (!match) return;

    const targetName = match[1];

    if (aiSelectedMarker) {
        aiSelectedMarker.setIcon(createInpostIcon(aiSelectedMarker.options._status, false));
        aiSelectedMarker = null;
    }

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
    const borderColor = isAiSelected           ? "#22c55e"
                      : status === "Operating"  ? "#ffd402"
                      : status === "Disabled"   ? "#e74c3c"
                      :                           "#95a5a6";

    const animClass = isAiSelected ? "ai-selected-marker" : "";

    return L.divIcon({
        html: `
            <div class="${animClass}" style="
                width:36px; height:36px;
                border-radius:50%;
                border:3px solid ${borderColor};
                background:#ffd402;
                display:flex; align-items:center; justify-content:center;
                box-shadow:0 2px 6px rgba(0,0,0,0.25);
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

const ICONS = {
    clock: `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>`,
    mapPin: `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
               fill="none" stroke="currentColor" stroke-width="2"
               stroke-linecap="round" stroke-linejoin="round">
               <path d="M20 10c0 6-8 13-8 13s-8-7-8-13a8 8 0 0 1 16 0Z"/>
               <circle cx="12" cy="10" r="3"/>
             </svg>`,
    check: `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 6 9 17l-5-5"/>
            </svg>`,
    x:     `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2.5"
              stroke-linecap="round" stroke-linejoin="round">
              <path d="M18 6 6 18M6 6l12 12"/>
            </svg>`,
    alert: `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>`,
};

function buildPopup(point) {
    const badgeClass  = point.status === "Operating" ? "badge-operating"
                      : point.status === "Disabled"  ? "badge-disabled"
                      :                                "badge-other";

    const statusIcon  = point.status === "Operating" ? ICONS.check
                      : point.status === "Disabled"  ? ICONS.x
                      :                                ICONS.alert;

    const statusLabel = point.status === "Operating" ? "Działa"
                      : point.status === "Disabled"  ? "Wyłączony"
                      :                                point.status;

    const imageHtml = point.image_url
        ? `<img class="popup-image" src="${point.image_url}"
                alt="${point.name}" onerror="this.style.display='none'">`
        : "";

    const descHtml = point.location_description
        ? `<div class="popup-row">${ICONS.mapPin} ${point.location_description}</div>`
        : "";

    return `
        <div class="popup-wrapper">
            ${imageHtml}
            <div class="popup-name">${point.name}</div>
            <div class="popup-address">${point.address || ""}, ${point.city || ""}</div>
            <div class="popup-row">
                <span class="badge ${badgeClass}">${statusIcon} ${statusLabel}</span>
            </div>
            <div class="popup-row">${ICONS.clock} ${point.opening_hours || "Brak danych"}</div>
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
        status.textContent = "Wpisz nazwę miasta";
        return;
    }

    status.textContent = "";
    markersLayer.clearLayers();
    showLoading("Szukam paczkomatów…");

    try {
        const params = new URLSearchParams({ city, ...getFilters() });
        const res    = await fetch(`/api/points/?${params}`);

        hideLoading();

        if (!res.ok) { status.textContent = "Błąd serwera"; return; }

        const data = await res.json();

        if (data.length === 0) {
            status.textContent = "Brak wyników — zmień filtry";
            return;
        }

        const bounds = [];
        data.forEach(point => {
            if (!point.lat || !point.lng) return;

            const marker = L.marker([point.lat, point.lng], {
                icon:    createInpostIcon(point.status),
                _name:   point.name,
                _status: point.status
            });

            marker.bindPopup(buildPopup(point), {
                maxWidth: 240, className: "inpost-popup"
            });

            markersLayer.addLayer(marker);
            bounds.push([point.lat, point.lng]);
        });

        if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });

        status.textContent = `Znaleziono ${data.length} punktów`;

    } catch (err) {
        hideLoading();
        console.error(err);
        status.textContent = "Błąd połączenia";
    }
}


// ══════════════════════════════════════════
//  MOJA LOKALIZACJA
// ══════════════════════════════════════════

function useMyLocation() {
    const status = document.getElementById("status");
    showLoading("Szukam Twojej lokalizacji…");

    navigator.geolocation.getCurrentPosition(
        async ({ coords: { latitude, longitude } }) => {
            map.setView([latitude, longitude], 13);

            L.marker([latitude, longitude], {
                icon: L.divIcon({
                    html: `<div style="
                        width:14px; height:14px;
                        background:#4285f4;
                        border:2.5px solid white;
                        border-radius:50%;
                        box-shadow:0 2px 6px rgba(0,0,0,0.4);
                    "></div>`,
                    className: "", iconSize: [14, 14], iconAnchor: [7, 7]
                })
            }).addTo(map).bindPopup("Twoja lokalizacja");

            try {
                const res  = await fetch(`/api/points/?lat=${latitude}&lng=${longitude}`);
                const data = await res.json();

                hideLoading();

                const bounds = [];
                data.forEach(point => {
                    if (!point.lat || !point.lng) return;
                    const marker = L.marker([point.lat, point.lng], {
                        icon:    createInpostIcon(point.status),
                        _name:   point.name,
                        _status: point.status
                    });
                    marker.bindPopup(buildPopup(point), {
                        maxWidth: 240, className: "inpost-popup"
                    });
                    markersLayer.addLayer(marker);
                    bounds.push([point.lat, point.lng]);
                });

                if (bounds.length) map.fitBounds(bounds, { padding: [40, 40] });
                status.textContent = `Znaleziono ${data.length} punktów w pobliżu`;

            } catch (err) {
                hideLoading();
                console.error(err);
                status.textContent = "Błąd połączenia";
            }
        },
        () => {
            hideLoading();
            status.textContent = "Brak dostępu do lokalizacji";
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
        hideAIThinking("Najpierw wyszukaj miasto.");
        return;
    }

    showAIThinking();

    try {
        const res  = await fetch("/api/ai/", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ query, city: cityInput })
        });
        const data = await res.json();
        console.log("[AI DEBUG]", data);
        hideAIThinking(data.recommendation || "Brak odpowiedzi.");

    } catch (err) {
        hideAIThinking("Błąd połączenia z AI.");
    }
}
