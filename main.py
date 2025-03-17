import logging
from io import BytesIO
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import folium
import gpxpy
import pykml.parser
import matplotlib.pyplot as plt
import os

# Basic logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)

TOKEN = "токен бота @BotFather"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Отправьте GPS-трек в формате GPX или KML, и я вернy визуализацию маршрута с отмеченными точками.\n /help"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Я могу обрабатывать GPS-треки в форматах GPX и KML.\n"
        "Просто отправьте мне файл трека, и я верну его визуализацию.\n"
        "Вы получите PNG-изображение трека с отмеченными точками и ссылку на маршрут.\n"
        "by addfix"
    )


def parse_gpx(file_content):
    gpx = gpxpy.parse(file_content)
    route_points = []
    waypoints = []
    waypoint_descriptions = {}

    # Get track points
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                route_points.append((point.latitude, point.longitude))
                if hasattr(point, "name") and point.name:
                    waypoints.append((point.latitude, point.longitude))
                    waypoint_descriptions[(point.latitude, point.longitude)] = (
                        point.name
                    )
                elif hasattr(point, "description") and point.description:
                    waypoints.append((point.latitude, point.longitude))
                    waypoint_descriptions[(point.latitude, point.longitude)] = (
                        point.description
                    )

    # Get route points
    for route in gpx.routes:
        for point in route.points:
            route_points.append((point.latitude, point.longitude))

    # Get waypoints
    for waypoint in gpx.waypoints:
        waypoints.append((waypoint.latitude, waypoint.longitude))
        description = waypoint.name if waypoint.name else "Точка"
        if waypoint.description:
            description += f": {waypoint.description}"
        waypoint_descriptions[(waypoint.latitude, waypoint.longitude)] = description

    # Create waypoints if none exist
    if not waypoints and route_points:
        num_points = len(route_points)
        if num_points > 0:
            waypoints.append(route_points[0])
            waypoint_descriptions[route_points[0]] = "Начало маршрута"

            if num_points > 10:
                step = max(1, num_points // 10)
                for i in range(step, num_points - 1, step):
                    waypoints.append(route_points[i])
                    waypoint_descriptions[route_points[i]] = f"Точка {i // step}"

            waypoints.append(route_points[-1])
            waypoint_descriptions[route_points[-1]] = "Конец маршрута"

    return {
        "route_points": route_points,
        "waypoints": waypoints,
        "descriptions": waypoint_descriptions,
    }


def parse_kml(file_content):
    root = pykml.parser.fromstring(file_content)
    route_points = []
    waypoints = []
    waypoint_descriptions = {}

    for placemark in root.findall(".//{http://www.opengis.net/kml/2.2}Placemark"):
        name = None
        description = None

        name_elem = placemark.find(".//{http://www.opengis.net/kml/2.2}name")
        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()

        desc_elem = placemark.find(".//{http://www.opengis.net/kml/2.2}description")
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip()

        coords_elem = placemark.find(".//{http://www.opengis.net/kml/2.2}coordinates")
        if coords_elem is not None:
            coords_text = coords_elem.text.strip()
            point_coords = []

            for coord in coords_text.split():
                parts = coord.split(",")
                if len(parts) >= 2:
                    lon, lat = float(parts[0]), float(parts[1])
                    point_coords.append((lat, lon))
                    route_points.append((lat, lon))

            if len(point_coords) == 1 and (name or description):
                waypoints.append(point_coords[0])
                desc = name if name else ""
                if description:
                    desc += f": {description}" if desc else description
                waypoint_descriptions[point_coords[0]] = desc or "Точка"

    if not waypoints and route_points:
        num_points = len(route_points)
        if num_points > 0:
            waypoints.append(route_points[0])
            waypoint_descriptions[route_points[0]] = "Начало маршрута"

            if num_points > 10:
                step = max(1, num_points // 10)
                for i in range(step, num_points - 1, step):
                    waypoints.append(route_points[i])
                    waypoint_descriptions[route_points[i]] = f"Точка {i // step}"

            waypoints.append(route_points[-1])
            waypoint_descriptions[route_points[-1]] = "Конец маршрута"

    return {
        "route_points": route_points,
        "waypoints": waypoints,
        "descriptions": waypoint_descriptions,
    }


def create_map(track_data):
    route_points = track_data["route_points"]
    waypoints = track_data["waypoints"]
    descriptions = track_data["descriptions"]

    if not route_points:
        return None

    # Find map center
    avg_lat = sum(p[0] for p in route_points) / len(route_points)
    avg_lon = sum(p[1] for p in route_points) / len(route_points)

    # Create Folium map
    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13)

    # Add route line
    folium.PolyLine(route_points, color="red", weight=2.5, opacity=1).add_to(m)

    # Add waypoint markers
    for i, point in enumerate(waypoints):
        description = descriptions.get(point, f"Точка {i+1}")
        folium.Marker(
            point, popup=description, icon=folium.Icon(icon="info-sign")
        ).add_to(m)

    temp_html = "temp_map.html"
    m.save(temp_html)

    return {
        "map": m,
        "center": (avg_lat, avg_lon),
        "route_points": route_points,
        "waypoints": waypoints,
        "descriptions": descriptions,
        "html_path": temp_html,
    }


def create_static_image(map_data):
    route_points = map_data["route_points"]
    waypoints = map_data["waypoints"]
    descriptions = map_data["descriptions"]

    # Define image boundaries
    lats = [p[0] for p in route_points]
    lons = [p[1] for p in route_points]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add padding
    padding = 0.05
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon
    min_lat -= lat_range * padding
    max_lat += lat_range * padding
    min_lon -= lon_range * padding
    max_lon += lon_range * padding

    # Create image
    fig, ax = plt.subplots(figsize=(12, 12))

    # Convert coordinates to pixels
    def normalize_coords(lat, lon):
        lat_norm = (lat - min_lat) / (max_lat - min_lat)
        lon_norm = (lon - min_lon) / (max_lon - min_lon)
        return lon_norm, lat_norm

    # Draw route line
    route_norm = [normalize_coords(lat, lon) for lat, lon in route_points]
    x_route = [p[0] for p in route_norm]
    y_route = [p[1] for p in route_norm]
    ax.plot(x_route, y_route, "r-", linewidth=2)

    # Set background color
    ax.set_facecolor("#f2f2e8")

    # Draw waypoints with numbers
    for i, waypoint in enumerate(waypoints):
        x, y = normalize_coords(waypoint[0], waypoint[1])
        ax.plot(x, y, "bo", markersize=10)

        ax.text(
            x,
            y,
            str(i + 1),
            fontsize=12,
            ha="center",
            va="center",
            bbox=dict(
                facecolor="white", alpha=0.8, edgecolor="none", boxstyle="circle"
            ),
        )

    ax.set_title("GPS-GPX/KML by addfix")
    plt.axis("off")

    # Save image to byte stream
    img_stream = BytesIO()
    plt.savefig(img_stream, format="png", bbox_inches="tight", dpi=150)
    img_stream.seek(0)
    plt.close(fig)

    return img_stream, waypoints


def create_maps_link(route_points):
    if not route_points or len(route_points) < 2:
        return None

    start = route_points[0]
    end = route_points[-1]

    link = f"https://www.google.com/maps/dir/?api=1&origin={start[0]},{start[1]}&destination={end[0]},{end[1]}"

    if len(route_points) > 2 and len(route_points) <= 25:
        waypoints = []
        step = max(1, len(route_points) // 23)
        for i in range(1, len(route_points) - 1, step):
            waypoints.append(f"{route_points[i][0]},{route_points[i][1]}")

        if waypoints:
            link += "&waypoints=" + "|".join(waypoints)

    return link


async def process_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message.document:
        await update.message.reply_text("Пожалуйста, отправьте GPX или KML файл.")
        return

    file = update.message.document
    file_name = file.file_name

    if not (file_name.endswith(".gpx") or file_name.endswith(".kml")):
        await update.message.reply_text(
            "Пожалуйста, отправьте файл в формате GPX или KML."
        )
        return

    await update.message.reply_text(
        "Обрабатываю файл. Это может занять несколько секунд..."
    )

    tg_file = await context.bot.get_file(file.file_id)
    file_content = BytesIO()
    await tg_file.download_to_memory(file_content)
    file_content.seek(0)

    try:
        track_data = {}
        if file_name.endswith(".gpx"):
            track_data = parse_gpx(file_content.read().decode("utf-8"))
        elif file_name.endswith(".kml"):
            track_data = parse_kml(file_content.read())

        if not track_data["route_points"]:
            await update.message.reply_text("Не удалось найти GPS точки в файле.")
            return

        map_data = create_map(track_data)
        if not map_data:
            await update.message.reply_text(
                "Не удалось создать карту из треков в файле."
            )
            return

        img_stream, waypoints = create_static_image(map_data)
        maps_link = create_maps_link(track_data["route_points"])

        await update.message.reply_photo(
            photo=img_stream,
            caption=f"Трек из файла {file_name}\nКоличество точек: {len(track_data['route_points'])}",
        )

        if maps_link:
            await update.message.reply_text(
                f"Ссылка на маршрут в Google Maps:\n{maps_link}"
            )

        if os.path.exists(map_data["html_path"]):
            os.remove(map_data["html_path"])

    except Exception as e:
        logging.error(f"Ошибка при обработке файла: {e}")
        await update.message.reply_text(
            f"Произошла ошибка при обработке файла: {str(e)}"
        )


def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, process_file))

    application.run_polling()


if __name__ == "__main__":
    main()
