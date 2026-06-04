const API_URL = "https://travel-golden-ring-ai.onrender.com";

// Для локального запуска можно временно заменить:
// const API_URL = "http://127.0.0.1:8000";

const cities = [
  "Сергиев Посад",
  "Переславль-Залесский",
  "Ростов Великий",
  "Ярославль",
  "Кострома",
  "Иваново",
  "Суздаль",
  "Владимир",
];

let selectedCity = null;

let map = null;
let markerSource = null;
let markerLayer = null;
let routeSource = null;
let routeLayer = null;
let popupOverlay = null;

const cityButtonsEl = document.getElementById("cityButtons");
const queryInput = document.getElementById("queryInput");
const askButton = document.getElementById("askButton");
const answerEl = document.getElementById("answer");
const statusEl = document.getElementById("status");
const selectedCityEl = document.getElementById("selectedCity");
const placesEl = document.getElementById("places");

const mapPopupEl = document.getElementById("mapPopup");
const mapPopupContentEl = document.getElementById("mapPopupContent");
const mapPopupCloseEl = document.getElementById("mapPopupClose");

function initCityButtons() {
  cityButtonsEl.innerHTML = "";

  cities.forEach((city) => {
    const btn = document.createElement("button");
    btn.className = "city-btn";
    btn.textContent = city;

    btn.addEventListener("click", () => {
      selectedCity = city;
      selectedCityEl.textContent = `Выбран город: ${city}`;

      document.querySelectorAll(".city-btn").forEach((item) => {
        item.classList.remove("active");
      });

      btn.classList.add("active");

      queryInput.value = `Что посмотреть в городе ${city}?`;
    });

    cityButtonsEl.appendChild(btn);
  });
}

function initQuickActions() {
  document.querySelectorAll(".quick-actions button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.dataset.prompt;

      if (selectedCity) {
        queryInput.value = `${prompt} в городе ${selectedCity}`;
      } else {
        queryInput.value = prompt;
      }

      askAssistant();
    });
  });
}

function initMap() {
  markerSource = new ol.source.Vector();
  routeSource = new ol.source.Vector();

  routeLayer = new ol.layer.Vector({
    source: routeSource,
    style: createRouteStyle(),
  });

  markerLayer = new ol.layer.Vector({
    source: markerSource,
    style: createMarkerStyle(),
  });

  const osmLayer = new ol.layer.Tile({
    source: new ol.source.OSM(),
  });

  map = new ol.Map({
    target: "map",
    layers: [osmLayer, routeLayer, markerLayer],
    view: new ol.View({
      center: ol.proj.fromLonLat([39.8, 56.9]),
      zoom: 6,
      minZoom: 5,
      maxZoom: 18,
    }),
    controls: ol.control.defaults.defaults({
      attribution: true,
      zoom: true,
      rotate: false,
    }),
  });

  popupOverlay = new ol.Overlay({
    element: mapPopupEl,
    positioning: "bottom-center",
    stopEvent: true,
    offset: [0, -24],
  });

  map.addOverlay(popupOverlay);

  mapPopupCloseEl.addEventListener("click", () => {
    popupOverlay.setPosition(undefined);
  });

  map.on("singleclick", (event) => {
    const feature = map.forEachFeatureAtPixel(event.pixel, (item) => item);

    if (!feature || feature.get("featureType") !== "place") {
      popupOverlay.setPosition(undefined);
      return;
    }

    const name = feature.get("name") || "Место";
    const city = feature.get("city") || "";
    const description = feature.get("description") || "";

    mapPopupContentEl.innerHTML = `
      <strong>${escapeHtml(name)}</strong>
      ${city ? `<br><span>${escapeHtml(city)}</span>` : ""}
      ${description ? `<p>${escapeHtml(description)}</p>` : ""}
    `;

    popupOverlay.setPosition(event.coordinate);
  });

  map.on("pointermove", (event) => {
    const hit = map.hasFeatureAtPixel(event.pixel);
    map.getTargetElement().style.cursor = hit ? "pointer" : "";
  });

  setGoldenRingMapView();
}

function createMarkerStyle() {
  return new ol.style.Style({
    image: new ol.style.Circle({
      radius: 9,
      fill: new ol.style.Fill({
        color: "#a3422b",
      }),
      stroke: new ol.style.Stroke({
        color: "#ffffff",
        width: 3,
      }),
    }),
  });
}

function createRouteStyle() {
  return new ol.style.Style({
    stroke: new ol.style.Stroke({
      color: "#a3422b",
      width: 4,
      lineDash: [8, 8],
    }),
  });
}

function setGoldenRingMapView() {
  if (!map) {
    return;
  }

  const goldenRingExtent = ol.extent.boundingExtent([
    ol.proj.fromLonLat([37.5, 55.8]),
    ol.proj.fromLonLat([41.5, 58.0]),
  ]);

  map.getView().fit(goldenRingExtent, {
    padding: [35, 35, 35, 35],
    maxZoom: 7,
    duration: 0,
  });
}

function setLoading(isLoading) {
  askButton.disabled = isLoading;
  askButton.textContent = isLoading ? "Думаю..." : "Спросить";
  statusEl.textContent = isLoading
    ? "Ассистент составляет ответ..."
    : "Готов к запросу";
}

function renderAnswer(data) {
  const answer = data.answer || "Ответ пустой.";

  if (window.marked) {
    answerEl.innerHTML = marked.parse(answer);
  } else {
    answerEl.textContent = answer;
  }
}

function renderPlaces(places) {
  placesEl.innerHTML = "";

  if (!places || places.length === 0) {
    placesEl.innerHTML = `
      <p class="empty-places">
        Ассистент не вернул отдельные места для карточек.
      </p>
    `;
    return;
  }

  places.forEach((place) => {
    const card = document.createElement("article");
    card.className = "place-card";

    const imageUrl =
      place.photo_url ||
      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/512px-No_image_available.svg.png";

    card.innerHTML = `
      <img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(place.name || "Место")}" loading="lazy">
      <div class="place-card__body">
        ${
          place.category
            ? `<span class="place-category">${escapeHtml(place.category)}</span>`
            : ""
        }
        <h3>${escapeHtml(place.name || "Без названия")}</h3>
        <p>${escapeHtml(place.description || "")}</p>
      </div>
    `;

    placesEl.appendChild(card);
  });
}

function clearMapObjects() {
  if (markerSource) {
    markerSource.clear();
  }

  if (routeSource) {
    routeSource.clear();
  }

  if (popupOverlay) {
    popupOverlay.setPosition(undefined);
  }
}

function normalizeNumber(value) {
  if (typeof value === "number") {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value.replace(",", "."));
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function renderMap(places) {
  if (!map || !markerSource || !routeSource) {
    return;
  }

  clearMapObjects();

  const features = [];
  const routeCoordinates = [];

  places.forEach((place) => {
    const lat = normalizeNumber(place.lat);
    const lon = normalizeNumber(place.lon);

    if (lat !== null && lon !== null) {
      const coordinates = ol.proj.fromLonLat([lon, lat]);

      const feature = new ol.Feature({
        geometry: new ol.geom.Point(coordinates),
        featureType: "place",
        name: place.name || "Место",
        city: place.city || "",
        description: place.description || "",
        category: place.category || "",
      });

      features.push(feature);
      routeCoordinates.push(coordinates);
    }
  });

  markerSource.addFeatures(features);

  if (routeCoordinates.length > 1) {
    const routeFeature = new ol.Feature({
      geometry: new ol.geom.LineString(routeCoordinates),
      featureType: "route",
    });

    routeSource.addFeature(routeFeature);
  }

  if (features.length === 0) {
    setGoldenRingMapView();
    return;
  }

  if (features.length === 1) {
    const coordinates = features[0].getGeometry().getCoordinates();

    map.getView().animate({
      center: coordinates,
      zoom: 13,
      duration: 700,
    });

    return;
  }

  const extent = markerSource.getExtent();

  map.getView().fit(extent, {
    padding: [80, 80, 80, 80],
    maxZoom: 14,
    duration: 800,
  });
}

async function askAssistant() {
  const query = queryInput.value.trim();

  if (!query) {
    alert("Введите вопрос или выберите быстрый запрос.");
    return;
  }

  setLoading(true);

  try {
    const response = await fetch(`${API_URL}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query,
        city: selectedCity,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(errorText);
    }

    const data = await response.json();

    renderAnswer(data);
    renderPlaces(data.places || []);
    renderMap(data.places || []);

    statusEl.textContent = "Ответ готов";
  } catch (error) {
    console.error(error);
    statusEl.textContent = "Ошибка";
    answerEl.textContent =
      "Произошла ошибка. Проверь backend, API_URL, index.json и ROUTERAI_API_KEY.";
  } finally {
    setLoading(false);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

askButton.addEventListener("click", askAssistant);

queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    askAssistant();
  }
});

window.addEventListener("load", () => {
  initCityButtons();
  initQuickActions();
  initMap();
});