import json

HERO_CATEGORIES_FILE = "hero_categories.json"

# hero_categoriesを保存する関数
def save_hero_categories(hero_categories, file_path=HERO_CATEGORIES_FILE):
    # set型をlist型に変換
    hero_categories_serializable = {
        key: list(value) if isinstance(value, set) else value
        for key, value in hero_categories.items()
    }
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(hero_categories_serializable, f, ensure_ascii=False, indent=4)

# hero_categoriesを読み込む関数
def load_hero_categories(file_path=HERO_CATEGORIES_FILE):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # リストをset型に戻す
            return {key: set(value) for key, value in data.items()}
    except FileNotFoundError:
        return {}  # ファイルがない場合は空の辞書を返す
        
def add_hero_to_tag(hero_categories, hero, tag=None):
    if tag is None:
        tag_list = ["All"]
    else:
        if tag not in hero_categories:
            print(f"エラー: '{tag}' というタグは存在しません。")
            return False  # タグが存在しない場合、追加は行わずFalseを返す
        tag_list = ["All", tag]

    added = False  # ヒーローが追加されたかどうかを追跡するフラグ

    for current_tag in tag_list:
        if current_tag not in hero_categories:
            print(f"エラー: '{current_tag}' というタグは存在しません。")
            return False  # タグが存在しない場合、追加は行わずFalseを返す

        if hero in hero_categories[current_tag]:
            print(f"'{hero}' は既に '{current_tag}' に追加されています。")
        else:
            hero_categories[current_tag].add(hero)
            print(f"'{hero}' を '{current_tag}' に追加しました。")
            added = True  # ヒーローが追加されたのでフラグをTrueに設定

    return added  # ヒーローが追加された場合Trueを返す

# ヒーローをタグから削除する関数
def remove_hero_from_tag(hero_categories, hero, tag=None):
    if tag is None:
        tag_list = ["All"]
    else:
        if tag not in hero_categories:
            print(f"エラー: '{tag}' というタグは存在しません。")
            return False  # タグが存在しない場合、削除は行わずFalseを返す
        tag_list = ["All", tag]

    removed = False  # ヒーローが削除されたかどうかを追跡するフラグ

    for current_tag in tag_list:
        if current_tag not in hero_categories:
            print(f"エラー: '{current_tag}' というタグは存在しません。")
            return False  # タグが存在しない場合、削除は行わずFalseを返す

        if hero not in hero_categories[current_tag]:
            print(f"'{hero}' は '{current_tag}' に存在しません。削除できません。")
        else:
            hero_categories[current_tag].remove(hero)
            print(f"'{hero}' を '{current_tag}' から削除しました。")
            removed = True  # ヒーローが削除されたのでフラグをTrueに設定

    return removed  # ヒーローが削除された場合Trueを返す
            
def add_hero_to_json(name,tag=None,file_path=HERO_CATEGORIES_FILE):
    hero_categories = load_hero_categories()
    added = add_hero_to_tag(hero_categories, name, tag)
    if added:
        save_hero_categories(hero_categories, file_path)
        print(f"'{file_path}' を更新しました。")
    else:
        print(f"'{file_path}' は更新されてません。")
        
# JSONファイルからヒーローを削除する関数
def remove_hero_from_json(name, tag=None, file_path=HERO_CATEGORIES_FILE):
    hero_categories = load_hero_categories()
    removed = remove_hero_from_tag(hero_categories, name, tag)
    if removed:
        save_hero_categories(hero_categories, file_path)
        print(f"'{file_path}' を更新しました。")
    else:
        print(f"'{file_path}' は更新されてません。")
        
        
# 指定したタグの中身を返す関数
def get_heroes_by_tag(tag, file_path=HERO_CATEGORIES_FILE):
    hero_categories = load_hero_categories()
    if tag not in hero_categories:
        print(f"エラー: '{tag}' というタグは存在しません。")
        return None  # タグが存在しない場合はNoneを返す
    return list(hero_categories[tag])  # タグに含まれるヒーローリストを返す
    