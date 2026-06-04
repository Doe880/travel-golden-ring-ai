// Для локального запуска:
const API_URL = "http://127.0.0.1:8000";

// Для Render после деплоя замени на свой адрес:
// const API_URL = "https://your-project-name.onrender.com";

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
let popupOverlay = null;

const cityButtonsEl = document.getElementById("cityButtons");
const queryInput = document.getElementById("queryInput");
const askButton = document.getElementById("askButton");
const answerEl = document.getElementById("answer");
const statusEl = document.getElementById("status");
const selectedCityEl = document.getElementById("selectedCity");
const placesEl = document.getElementById("places");
const sourcesEl = document.getElementById("sources");

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

  markerLayer = new ol.layer.Vector({
    source: markerSource,
    style: createMarkerStyle(),
  });

  const osmLayer = new ol.layer.Tile({
    source: new ol.source.OSM(),
  });

  map = new ol.Map({
    target: "map",
    layers: [
      osmLayer,
      markerLayer,
    ],
    view: new ol.View({
      // OpenLayers работает в проекции Web Mercator.
      // fromLonLat принимает [longitude, latitude].
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

    if (!feature) {
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
  answerEl.textContent = data.answer || "Ответ пустой.";

  if (data.sources && data.sources.length > 0) {
    sourcesEl.innerHTML = `
      <strong>Источники из базы знаний:</strong>
      <ul>
        ${data.sources.map((source) => `<li>${escapeHtml(source)}</li>`).join("")}
      </ul>
    `;
  } else {
    sourcesEl.innerHTML = "";
  }
}

function renderPlaces(places) {
  placesEl.innerHTML = "";

  if (!places || places.length === 0) {
    placesEl.innerHTML = `<p>Ассистент не вернул отдельные места для карточек.</p>`;
    return;
  }

  places.forEach((place) => {
    const card = document.createElement("article");
    card.className = "place-card";

    const imageUrl =
      place.photo_url ||
      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/No_image_available.svg/512px-No_image_available.svg.png";

    card.innerHTML = `
      <img src="${imageUrl}" alt="${escapeHtml(place.name || "Место")}" loading="lazy">
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

function clearMapMarkers() {
  if (markerSource) {
    markerSource.clear();
  }

  if (popupOverlay) {
    popupOverlay.setPosition(undefined);
  }
}

function renderMap(places) {
  if (!map || !markerSource) {
    return;
  }

  clearMapMarkers();

  const features = [];

  places.forEach((place) => {
    if (typeof place.lat === "number" && typeof place.lon === "number") {
      const coordinates = ol.proj.fromLonLat([place.lon, place.lat]);

      const feature = new ol.Feature({
        geometry: new ol.geom.Point(coordinates),
        name: place.name || "Место",
        city: place.city || "",
        description: place.description || "",
        category: place.category || "",
      });

      features.push(feature);
    }
  });

  markerSource.addFeatures(features);

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
      "Произошла ошибка. Проверь, запущен ли backend, правильно ли указан API_URL, создан ли index.json и указан ли OPENROUTER_API_KEY.";
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