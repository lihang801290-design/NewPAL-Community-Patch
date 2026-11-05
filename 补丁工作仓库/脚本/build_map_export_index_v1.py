"""Build the master export index: scene -> map resource -> image files.

Outputs JSON, CSV, SQLite and a human-readable README under 地图开发/地图索引/.
All image paths are stored relative to the patch repository so the index can
move with the project.

The archive entry table (offset/size per map_resource_id) is re-scanned from
huge.lmf / huge2.lmf on every run, because 原生碎片解包记录.json only keeps the
decoded fields (size, layers, hashes) and not the byte offsets.
"""
import csv
import json
import sqlite3
import struct
from datetime import datetime
from pathlib import Path

BASE = Path(r"N:\steam\steamapps\common\NewPAL\补丁工作仓库")
GAME = BASE.parent
SCENES = BASE / "地图开发" / "全场景对象布置核对.json"
EXTRACT = BASE / "地图开发" / "原生碎片解包记录.json"
ART_CACHE = BASE / "地图开发" / "原生原画缓存"
COLLISION_CACHE = BASE / "地图开发" / "原生碎片缓存"
COLLISION_TREE = BASE / "网页下载地图" / "按英雄网顺序分类"
ART_TREE = BASE / "网页下载地图" / "按英雄网顺序原画分类"
CATALOG = COLLISION_TREE / "分类清单.json"
FLOORS = BASE / "地图开发" / "楼层归属判定.json"
GMAP = BASE / "地图开发" / "RE" / "gmap_entries.json"
OUT = BASE / "地图开发" / "地图索引"
ARCHIVES = ("huge.lmf", "huge2.lmf")
TILE_PIXELS = 16
TILE_WORLD_UNITS = 16


def rel(path):
    return Path(path).resolve().relative_to(BASE.resolve()).as_posix()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def scan_archive(path):
    """Read the trailing entry table and each resource header only."""
    rows = {}
    total = path.stat().st_size
    with path.open("rb") as handle:
        index = struct.unpack("<I", handle.read(4))[0]
        count = (total - index - 1) >> 4
        handle.seek(index)
        table = handle.read(count * 16)
        for position in range(count):
            offset, length, resource_id, _ = struct.unpack_from("<4I", table, position * 16)
            if offset < 4 or length < 0x118 or offset + length > total:
                continue
            handle.seek(offset)
            head = handle.read(0x404)
            if head[:4] != b"MSF3":
                continue
            width, height, depth, tag, layers = struct.unpack_from("<5H", head, 0x104)
            if not (0 < width <= 4096 and 0 < height <= 4096 and depth in (8, 16)):
                continue
            rows[resource_id] = dict(
                archive=path.name, offset=offset, size=length,
                width=width, height=height, color_depth=depth, tag=tag, layers=layers,
            )
    return rows


def scan_all_archives():
    merged = {}
    for name in ARCHIVES:
        path = GAME / name
        if not path.exists():
            continue
        for resource_id, row in scan_archive(path).items():
            merged.setdefault(resource_id, row)
    return merged


def atlas_header(archive_name, offset):
    """Read only the resource and atlas headers, not the full archive."""
    path = GAME / archive_name
    with path.open("rb") as handle:
        handle.seek(offset + 0x3C)
        atlas_offset = struct.unpack("<I", handle.read(4))[0]
        handle.seek(offset + atlas_offset)
        header = handle.read(0x400)
    if len(header) != 0x400:
        return None
    chunk_size, total_size = struct.unpack_from("<2I", header, 4)
    count = 0
    for index in range(50):
        source_offset, packed_size = struct.unpack_from("<2I", header, 0x10 + index * 8)
        if source_offset == 0 and packed_size == 0:
            break
        count += 1
    return dict(atlas_offset=atlas_offset, chunk_size=chunk_size,
                total_size=total_size, chunk_count=count)


def load_floor_assignment():
    """Scene -> floor category, as decided by match_floor_scenes_v1.py."""
    if not FLOORS.exists():
        return {}
    assignment = {}
    for group in read_json(FLOORS)["groups"]:
        for category in group["categories"]:
            for scene_id, score, margin in zip(
                    category["assigned_scenes"], category["assigned_scores"], category["margin"]):
                assignment[scene_id] = dict(
                    group=group["key"], folder=category["folder"], name=category["name"],
                    score=score, margin=margin)
    return assignment


def load_gmap_group():
    """Scene -> (area id, entry count) from the GMap.dat parse.

    GMap.dat is the tenth table loaded by PAL_LoadGameDataTables. Its trailing
    triple groups scenes that share one area/tileset (all ten 鎖妖塔 floors land
    on 15045, the whole 黑蜘蛛森林 on 15042), which is the only dungeon-level
    grouping the game data gives us for free.
    """
    if not GMAP.exists():
        return {}
    rows = {}
    for scene_id, entries in read_json(GMAP)["scenes"].items():
        rows[int(scene_id)] = dict(group=entries[-1]["triple"][0], count=len(entries))
    return rows


def collect_tree(root, subdir, manifest_name, collector, extra_keys=()):
    """Walk per-category manifests and collect records by scene ID.

    A scene can appear on more than one guide map (羅剎山洞 has two visits),
    so every occurrence is kept; the first one becomes the primary path.
    """
    for path in sorted(root.glob(f"*/{subdir}/{manifest_name}")):
        payload = read_json(path)
        for fragment in payload["fragments"]:
            record = dict(
                category_folder=payload["folder"], category_name=payload["category"],
                region=payload["region"],
                image=rel(path.parent / fragment["file"]),
                image_pixels=fragment.get("image_pixels"),
                image_sha256=fragment.get("image_sha256"),
            )
            for key in extra_keys:
                record[key] = payload.get(key)
            collector.setdefault(fragment["scene_id"], []).append(record)


def main():
    scenes_meta = read_json(SCENES)["scenes"]
    extract = read_json(EXTRACT)["resources"]
    catalog = read_json(CATALOG)
    archive_rows = scan_all_archives()

    floors = load_floor_assignment()
    gmap = load_gmap_group()
    collision_by_scene = {}
    art_by_scene = {}
    collect_tree(COLLISION_TREE, "原生碎片", "碎片清单.json", collision_by_scene,
                 extra_keys=("floor_assignment",))
    collect_tree(ART_TREE, "原生原画", "原画清单.json", art_by_scene)

    # Base artwork and animation frames from the central cache.
    art_entries = {}
    for path in sorted(ART_CACHE.glob("三层动画帧*清单.json")):
        payload = read_json(path)
        for entry in payload["maps"]:
            if "error" not in entry:
                art_entries.setdefault(entry["resource_id"], []).append(entry)
    base_manifest = read_json(ART_CACHE / "原生原画清单.json")
    for entry in base_manifest["maps"]:
        if "error" not in entry:
            art_entries.setdefault(entry["resource_id"], []).append(entry)

    resource_ids = set(archive_rows)
    resource_ids.update(int(key) for key in extract)
    resource_ids.update(scene["map_resource_id"] for scene in scenes_meta)
    resources = {}
    for resource_id in sorted(resource_ids):
        packed = archive_rows.get(resource_id)
        info = extract.get(str(resource_id)) or {}
        frames = sorted(art_entries.get(resource_id, []), key=lambda item: item.get("frame", 0))
        base = next((frame for frame in frames if frame.get("frame", 0) == 0), None)
        if packed:
            record = dict(
                resource_id=resource_id, exists_in_archive=True,
                archive=packed["archive"], archive_offset=packed["offset"],
                archive_size=packed["size"],
                width=packed["width"], height=packed["height"],
                layers=packed["layers"], color_depth=packed["color_depth"],
                tag=packed["tag"],
                grid_pixels=[packed["width"] * TILE_PIXELS, packed["height"] * TILE_PIXELS],
                distinct_cells=info.get("distinct_cells"),
                grid_sha256=info.get("grid_sha256"),
                collision_cache=rel(COLLISION_CACHE / info["image"]) if info.get("image") else None,
                artwork_cache=rel(base["output"]) if base else None,
                artwork_frames=[dict(frame=frame.get("frame", 0),
                                     image=rel(frame["output"]),
                                     image_pixels=frame["image_pixels"]) for frame in frames],
                atlas=atlas_header(packed["archive"], packed["offset"]),
                category_folders=[], scenes=[],
            )
            if base:
                record["artwork_image_pixels"] = base["image_pixels"]
        else:
            record = dict(
                resource_id=resource_id, exists_in_archive=False,
                archive=None, archive_offset=None, archive_size=None,
                width=None, height=None, layers=None, color_depth=None, tag=None,
                grid_pixels=None, distinct_cells=None, grid_sha256=None,
                collision_cache=None, artwork_cache=None,
                artwork_frames=[], atlas=None, category_folders=[], scenes=[],
                note="scene table references this resource, but no MSF3 entry exists in huge.lmf/huge2.lmf",
            )
        resources[resource_id] = record

    scene_rows = []
    object_rows = []
    for scene in scenes_meta:
        scene_id = scene["scene_id"]
        resource_id = scene["map_resource_id"]
        resource = resources[resource_id]
        collision_set = collision_by_scene.get(scene_id) or []
        artwork_set = art_by_scene.get(scene_id) or []
        collision = collision_set[0] if collision_set else None
        artwork = artwork_set[0] if artwork_set else None
        categories = sorted({item["category_folder"] for item in collision_set + artwork_set})
        if categories:
            resource["category_folders"] = sorted(set(resource["category_folders"]) | set(categories))
        resource["scenes"].append(scene_id)
        artwork_path = artwork["image"] if artwork else resource["artwork_cache"]
        artwork_pixels = artwork["image_pixels"] if artwork else resource.get("artwork_image_pixels")
        collision_path = collision["image"] if collision else resource["collision_cache"]
        scene_rows.append(dict(
            scene_id=scene_id, native_name=scene["native_name"],
            map_resource_id=resource_id, map_exists=resource["exists_in_archive"],
            grid_width=resource["width"], grid_height=resource["height"],
            image_width=artwork_pixels[0] if artwork_pixels else None,
            image_height=artwork_pixels[1] if artwork_pixels else None,
            grid_pixels=resource["grid_pixels"],
            category_folders=categories,
            category_name=(collision or artwork or {}).get("category_name"),
            region=(collision or artwork or {}).get("region"),
            collision_image=collision_path,
            collision_images=[item["image"] for item in collision_set]
                             or ([collision_path] if collision_path else []),
            artwork_image=artwork_path,
            artwork_images=[item["image"] for item in artwork_set]
                            or ([artwork_path] if artwork_path else []),
            artwork_frames=resource["artwork_frames"],
            native_descriptor=scene.get("native_descriptor"),
            floor_assignment=(collision or {}).get("floor_assignment"),
            floor_group=(floors.get(scene_id) or {}).get("group"),
            floor_category=(floors.get(scene_id) or {}).get("folder"),
            floor_name=(floors.get(scene_id) or {}).get("name"),
            floor_score=(floors.get(scene_id) or {}).get("score"),
            floor_margin=(floors.get(scene_id) or {}).get("margin"),
            gmap_group=(gmap.get(scene_id) or {}).get("group"),
            gmap_entry_count=(gmap.get(scene_id) or {}).get("count"),
            placed_object_count=len(scene.get("placed_objects") or []),
        ))
        scene_objects = []
        for order, obj in enumerate(scene.get("placed_objects") or []):
            grid = obj.get("grid_xy") or [None, None]
            raw = obj.get("raw_words") or []
            row = dict(
                scene_id=scene_id, order=order, actor_id=obj.get("actor_id"),
                type_word=raw[2] if len(raw) > 2 else None,
                grid_x=grid[0], grid_y=grid[1],
                pixel_x=grid[0] * TILE_PIXELS if grid[0] is not None else None,
                pixel_y=grid[1] * TILE_PIXELS if grid[1] is not None else None,
                trigger_parameter=obj.get("trigger_parameter"),
                route_parameter=obj.get("route_parameter"),
                flags=obj.get("flags"),
                raw_words=raw,
            )
            object_rows.append(row)
            scene_objects.append({key: row[key] for key in (
                "actor_id", "type_word", "grid_x", "grid_y", "pixel_x", "pixel_y",
                "trigger_parameter", "route_parameter", "flags")})
        scene_rows[-1]["objects"] = scene_objects

    floor_scenes = {}
    for row in scene_rows:
        if row["floor_category"]:
            floor_scenes.setdefault(row["floor_category"], []).append(row["scene_id"])

    category_rows = []
    for entry in catalog["maps"]:
        scene_ids = [row["scene_id"] for row in scene_rows
                     if entry["folder"] in row["category_folders"]]
        category_rows.append(dict(
            order=entry["order"], folder=entry["folder"], name=entry["name"], region=entry["region"],
            collision_dir=rel(COLLISION_TREE / entry["folder"] / "原生碎片"),
            artwork_dir=rel(ART_TREE / entry["folder"] / "原生原画"),
            guide_dir=rel(ART_TREE / entry["folder"] / "攻略图"),
            scene_count=len(scene_ids),
            floor_assignment=entry.get("floor_assignment"),
            scene_ids=scene_ids,
            assigned_scene_ids=sorted(floor_scenes.get(entry["folder"], [])),
        ))

    runtime = dict(
        scene_id_address="0x0053D064",
        leader_index_address="0x0053A5FC",
        leader_object_base="0x0053E8C8",
        leader_object_stride=0x48,
        leader_world_x_offset=0x04,
        leader_world_y_offset=0x06,
        camera_note="0x0056C100/0x0056C104 are camera offsets, not player coordinates",
        world_units_per_tile=TILE_WORLD_UNITS,
        image_pixels_per_tile=TILE_PIXELS,
        image_pixels_per_world_unit=1,
        formula=("pixel_x = leader_world_x; pixel_y = leader_world_y "
                 "(relative to map origin; validate against a running scene)"),
        object_formula="pixel_x = grid_x * 16; pixel_y = grid_y * 16",
        lookup="scene_export_index.sqlite: SELECT * FROM scenes WHERE scene_id = ?",
    )
    index = dict(
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        path_base_absolute=str(BASE),
        path_rule="all image paths are POSIX-style paths relative to path_base_absolute",
        counts=dict(
            scenes=len(scene_rows),
            resources_in_archive=sum(1 for item in resources.values() if item["exists_in_archive"]),
            resources_referenced=len(resources),
            categories=len(category_rows),
            classified_scenes=sum(1 for row in scene_rows if row["category_folders"]),
            floor_assigned_scenes=sum(1 for row in scene_rows if row["floor_category"]),
            missing_resource_scenes=sum(1 for row in scene_rows if not row["map_exists"]),
            placed_objects=len(object_rows),
            gmap_grouped_scenes=sum(1 for row in scene_rows if row["gmap_group"] is not None),
            gmap_groups=len({row["gmap_group"] for row in scene_rows if row["gmap_group"] is not None}),
        ),
        runtime=runtime,
        scenes=scene_rows,
        resources=list(resources.values()),
        categories=category_rows,
    )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scene_export_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "map_resource_export_index.json").write_text(
        json.dumps(list(resources.values()), ensure_ascii=False, indent=2), encoding="utf-8")

    with (OUT / "scene_export_index.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["scene_id", "native_name", "map_resource_id", "map_exists", "category_folders",
                  "category_name", "region", "grid_width", "grid_height", "image_width",
                  "image_height", "placed_object_count", "collision_image", "collision_images",
                  "artwork_image", "artwork_images", "floor_assignment",
                  "floor_group", "floor_category", "floor_name", "floor_score",
                  "gmap_group", "gmap_entry_count"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in scene_rows:
            flat = dict(row)
            flat["category_folders"] = "|".join(row["category_folders"])
            flat["collision_images"] = "|".join(row["collision_images"])
            flat["artwork_images"] = "|".join(row["artwork_images"])
            writer.writerow(flat)

    with (OUT / "map_resource_export_index.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["resource_id", "exists_in_archive", "archive", "archive_offset", "archive_size",
                  "width", "height", "layers", "color_depth", "distinct_cells",
                  "collision_cache", "artwork_cache", "artwork_frames",
                  "category_folders", "scenes"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for resource in resources.values():
            flat = dict(resource)
            flat["artwork_frames"] = "|".join(
                f"{frame['frame']}:{frame['image']}" for frame in resource["artwork_frames"])
            flat["category_folders"] = "|".join(resource["category_folders"])
            flat["scenes"] = "|".join(str(value) for value in resource["scenes"])
            writer.writerow(flat)

    with (OUT / "scene_objects.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["scene_id", "order", "actor_id", "type_word", "grid_x", "grid_y",
                  "pixel_x", "pixel_y", "trigger_parameter", "route_parameter", "flags"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(object_rows)

    database = OUT / "scene_export_index.sqlite"
    if database.exists():
        database.unlink()
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE scenes (
            scene_id INTEGER PRIMARY KEY, native_name TEXT, map_resource_id INTEGER,
            map_exists INTEGER, category_folders TEXT, category_name TEXT, region TEXT,
            grid_width INTEGER, grid_height INTEGER, image_width INTEGER, image_height INTEGER,
            collision_image TEXT, collision_images TEXT,
            artwork_image TEXT, artwork_images TEXT, artwork_frames TEXT,
            native_descriptor TEXT, floor_assignment TEXT, placed_object_count INTEGER,
            floor_group TEXT, floor_category TEXT, floor_name TEXT,
            floor_score REAL, floor_margin REAL,
            gmap_group INTEGER, gmap_entry_count INTEGER
        );
        CREATE TABLE resources (
            resource_id INTEGER PRIMARY KEY, exists_in_archive INTEGER, archive TEXT,
            archive_offset INTEGER, archive_size INTEGER, width INTEGER, height INTEGER,
            layers INTEGER, color_depth INTEGER, distinct_cells INTEGER,
            collision_cache TEXT, artwork_cache TEXT, artwork_frames TEXT,
            atlas_total_size INTEGER, atlas_chunk_count INTEGER,
            category_folders TEXT, scenes TEXT
        );
        CREATE TABLE categories (
            "order" INTEGER PRIMARY KEY, folder TEXT, name TEXT, region TEXT,
            collision_dir TEXT, artwork_dir TEXT, guide_dir TEXT,
            scene_count INTEGER, floor_assignment TEXT, scene_ids TEXT,
            assigned_scene_ids TEXT
        );
        CREATE TABLE objects (
            scene_id INTEGER, "order" INTEGER, actor_id INTEGER, type_word INTEGER,
            grid_x INTEGER, grid_y INTEGER, pixel_x INTEGER, pixel_y INTEGER,
            trigger_parameter INTEGER, route_parameter INTEGER, flags INTEGER,
            PRIMARY KEY (scene_id, "order")
        );
        CREATE INDEX idx_scenes_resource ON scenes(map_resource_id);
        CREATE INDEX idx_scenes_category ON scenes(category_folders);
        CREATE INDEX idx_objects_actor ON objects(actor_id);
        CREATE INDEX idx_objects_type ON objects(type_word);
        CREATE VIEW scene_lookup AS
            SELECT scene_id, native_name, map_resource_id, category_name,
                   artwork_image, collision_image, grid_width, grid_height
            FROM scenes;
        CREATE VIEW object_lookup AS
            SELECT o.scene_id, s.native_name, s.artwork_image, o.actor_id, o.type_word,
                   o.grid_x, o.grid_y, o.pixel_x, o.pixel_y, s.grid_width, s.grid_height
            FROM objects o JOIN scenes s USING (scene_id);
    """)
    connection.executemany("INSERT INTO metadata VALUES (?,?)", [
        ("generated_at", index["generated_at"]),
        ("path_base_absolute", index["path_base_absolute"]),
        ("path_rule", index["path_rule"]),
        ("runtime_json", json.dumps(runtime, ensure_ascii=False)),
    ])
    connection.executemany(
        "INSERT INTO scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(row["scene_id"], row["native_name"], row["map_resource_id"], int(row["map_exists"]),
          "|".join(row["category_folders"]), row["category_name"], row["region"],
          row["grid_width"], row["grid_height"], row["image_width"], row["image_height"],
          row["collision_image"], "|".join(row["collision_images"]),
          row["artwork_image"], "|".join(row["artwork_images"]),
          json.dumps(row["artwork_frames"], ensure_ascii=False),
          json.dumps(row["native_descriptor"], ensure_ascii=False),
          row["floor_assignment"], row["placed_object_count"],
          row["floor_group"], row["floor_category"], row["floor_name"],
          row["floor_score"], row["floor_margin"],
          row["gmap_group"], row["gmap_entry_count"]) for row in scene_rows])
    connection.executemany(
        "INSERT INTO resources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [(item["resource_id"], int(item["exists_in_archive"]), item["archive"],
          item["archive_offset"], item["archive_size"], item["width"], item["height"],
          item["layers"], item["color_depth"], item["distinct_cells"],
          item["collision_cache"], item["artwork_cache"],
          json.dumps(item["artwork_frames"], ensure_ascii=False),
          item["atlas"]["total_size"] if item["atlas"] else None,
          item["atlas"]["chunk_count"] if item["atlas"] else None,
          "|".join(item["category_folders"]), "|".join(str(v) for v in item["scenes"]))
         for item in resources.values()])
    connection.executemany(
        "INSERT INTO categories VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(item["order"], item["folder"], item["name"], item["region"],
          item["collision_dir"], item["artwork_dir"], item["guide_dir"],
          item["scene_count"], item["floor_assignment"],
          "|".join(str(value) for value in item["scene_ids"]),
          "|".join(str(value) for value in item["assigned_scene_ids"])) for item in category_rows])
    connection.executemany(
        "INSERT INTO objects VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(row["scene_id"], row["order"], row["actor_id"], row["type_word"],
          row["grid_x"], row["grid_y"], row["pixel_x"], row["pixel_y"],
          row["trigger_parameter"], row["route_parameter"], row["flags"])
         for row in object_rows])
    connection.commit()
    connection.close()

    missing = sorted({row["map_resource_id"] for row in scene_rows if not row["map_exists"]})
    multi_frame = sorted(item["resource_id"] for item in resources.values()
                         if len(item["artwork_frames"]) > 1)
    lines = [
        "# 地图导出索引", "",
        f"生成时间：{index['generated_at']}", "",
        "这份索引把运行时场景、地图资源、碰撞结构图、原生原画、对象布置和分类目录全部对应起来，"
        "供未来的角色位置/地图系统直接查表。", "",
        "## 文件", "",
        "| 文件 | 用途 |", "|---|---|",
        f"| `scene_export_index.json` | {index['counts']['scenes']} 个场景的完整主索引（含对象布置与动画帧路径） |",
        f"| `map_resource_export_index.json` | {index['counts']['resources_in_archive']} 个归档地图资源 + 场景引用但归档不存在的占位记录 |",
        "| `scene_export_index.csv` | 场景表，可用 Excel/WPS 打开 |",
        "| `map_resource_export_index.csv` | 资源表，可用 Excel/WPS 打开 |",
        f"| `scene_objects.csv` | {index['counts']['placed_objects']} 条场景对象布置（actor_id / 格坐标 / 像素坐标） |",
        "| `scene_export_index.sqlite` | 可直接供程序查询的 SQLite 数据库 |", "",
        "所有图片路径均相对补丁仓库根目录，路径分隔符统一为 `/`。", "",
        "## 关键关系", "",
        "- 运行时先读场景 ID：`0x0053D064`。",
        "- 用 `scene_id` 查 `scenes` 表，得到 `map_resource_id`、分类目录、碰撞图和原画路径。",
        "- 角色位置读 `0x0053A5FC` 取领队索引，再读 `0x0053E8C8 + index*0x48` 的 `+4/+6` WORD（世界 X/Y）。",
        "- 地图每格 16 世界单位，原画每格 16 像素；在未缩放底图上，`pixel_x = world_x`、`pixel_y = world_y`（相对地图原点）。该 1:1 关系需在运行场景中再实测确认。",
        "- 场景内物件/入口/NPC 的格坐标在 `objects` 表，`pixel = grid * 16`，可直接叠到原画上。",
        "- `0x0056C100/0x0056C104` 是镜头偏移，不是角色坐标。", "",
        "## 坐标口径（重要）", "",
        "原画是游戏预渲染的 2.5D 背景，不是正交俯视贴图：室内场景（如余杭客栈 1 号）墙面有明显透视收缩，"
        "锁妖塔这类场景接近正俯视。因此：", "",
        "- **网格坐标是权威值**：`grid_x/grid_y` 来自场景布置表，与原画尺寸严格成 16 倍关系，任何场景都可靠。",
        "- **像素坐标是近似投影**：`pixel = grid*16` 在正俯视场景基本重合，在强透视场景只落在正确邻域。"
        "做地图 UI 时请以网格坐标为准，需要像素级贴合时按场景做一次单应变换标定。",
        "- 已被 `脚本/preview_scene_overlay_v1.py` 目视核对：场景 1 的 10 个物件落在床边/柜台/门口；"
        "场景 195 的中央物件 `6677` 正好压在太极图上，其余分布在走廊地面。", "",
        "## 查询示例", "",
        "```sql",
        "-- 场景 195 = 锁妖塔第一层：两条图路径一次拿到",
        "SELECT native_name, artwork_image, collision_image, category_name",
        "FROM scenes WHERE scene_id = 195;",
        "",
        "-- 该场景所有物件在原画上的像素位置",
        "SELECT actor_id, grid_x, grid_y, pixel_x, pixel_y FROM objects WHERE scene_id = 195;",
        "",
        "-- 反查：某个 actor 出现在哪些地图上",
        "SELECT scene_id, native_name, artwork_image FROM object_lookup WHERE actor_id = 9004;",
        "",
        "-- 按类型统计：type_word 才是“怪/物品种类”，actor_id 只是每处唯一实例",
        "SELECT type_word, COUNT(*) n, COUNT(DISTINCT scene_id) scenes",
        "FROM objects GROUP BY type_word ORDER BY n DESC LIMIT 20;",
        "",
        "-- 按 GMap 图块组分组：同一图块集的场景会落到同一个 gmap_group（第一槽位）",
        "SELECT gmap_group, COUNT(*) n, GROUP_CONCAT(scene_id) ids, GROUP_CONCAT(DISTINCT native_name) names",
        "FROM scenes WHERE gmap_group IS NOT NULL GROUP BY gmap_group ORDER BY n DESC;",
        "```", "",
        "```python",
        "import sqlite3",
        "from pathlib import Path",
        "base = Path(r'" + str(BASE) + "')",
        "db = sqlite3.connect(base / '地图开发/地图索引/scene_export_index.sqlite')",
        "db.row_factory = sqlite3.Row",
        "scene = db.execute('SELECT * FROM scenes WHERE scene_id=?', (scene_id,)).fetchone()",
        "artwork = base / scene['artwork_image']",
        "```", "",
        "## 配套工具", "",
        "| 脚本 | 作用 |", "|---|---|",
        "| `脚本/build_map_export_index_v1.py` | 重建本目录全部产物（会重新扫描 huge.lmf/huge2.lmf 取 offset/size） |",
        "| `脚本/preview_scene_overlay_v1.py 195` | 把某场景的物件叠到原画上，输出到 `地图开发/原画验证/scene_XXXX_overlay.png` |",
        "| `脚本/parse_gmap_v1.py` | 解析 `GMap.dat`，产出 `地图开发/RE/gmap_entries.json`（`gmap_group` 的来源） |",
        "| `脚本/decode_msf3_artwork_v1.py` | 重新解出原生原画（`--all-single-layer` / `--frame`） |", "",
        "分类目录、图或场景表任何一边改动后，重跑构建脚本即可，索引不需要手工维护。", "",
        "## 统计", "",
        f"- 场景：{index['counts']['scenes']} 条（场景 ID 唯一）",
        f"- 归档地图资源：{index['counts']['resources_in_archive']} 个",
        f"- 场景引用但归档不存在的资源：{len(missing)} 个 {missing}",
        f"- 分类目录：{index['counts']['categories']} 个",
        f"- 已归入 50 类目录的场景：{index['counts']['classified_scenes']} 条",
        f"- 场景对象布置：{index['counts']['placed_objects']} 条",
        f"- 已判定楼层归属的场景：{index['counts']['floor_assigned_scenes']} 条（将军冢 3 层、试炼之窟 7 层 ×2 场景、神殿 5 座）",
        f"- 有 GMap 图块组编号的场景：{index['counts']['gmap_grouped_scenes']} 条，共 {index['counts']['gmap_groups']} 个不同取值",
        f"- 多帧（三层动画）资源：{len(multi_frame)} 个 {multi_frame}", "",
        "## 注意", "",
        "- `scene_id` 与 `map_resource_id` 不是同一个编号，不能混用。",
        "- **`actor_id` 是实例号，不是类型号**：4111 条布置的 `actor_id` 全不重复，同一类怪在不同场景编号不同。"
        "布置表第 3 个字（`type_word`，278 种取值，699 出现在 322 个场景、700 出现在 138 个）是分类用的候选键，"
        "但其语义尚未逐个确认，不能直接称为“怪物类型”。做分类请按 `type_word` 聚合，不要按 `actor_id`。",
        "- 4 个三层资源是动画帧，`artwork_frames` 记录第 0/1/2 帧；静态地图用第 0 帧。",
        "- 原画只含地图格瓦片，不含人物/物件精灵；角色图标应由补丁叠加，位置取 `objects` 表。",
        "- 未归类的场景仍可通过中央缓存路径查到底图，索引不会丢图。",
        "- 多层迷宫的楼层归属已判定（`floor_group` / `floor_category`）；仍未确定的是「层与层之间的楼梯通向哪里」，"
        "那部分不在任何数据表里，在脚本 VM 内（见 `地图开发/RE/GMap.dat_分析.md`）。",
        "- `gmap_group` 来自 `GMap.dat`：**图块集编号**，每场景有 1–3 个槽位，此处取第一槽位。"
        "取值 15001–15070、共 61 种，与资源 id（1–877）不是同一套编号。同图块集的场景多为同一处（鎖妖塔二至十层同为 15045、"
        "黑蜘蛛森林 39 个场景同为 15042），但**不严格按洞窟**——将军冢三层分别是 15018/15019/15020。它不是楼梯连接，也不是场景号。",
    ]
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(index["counts"], ensure_ascii=False))
    print("index=", OUT)


if __name__ == "__main__":
    main()
