# calculate_tool の機能を直接インポート可能に
from .calculate_tool import add_info_to_heroes

# list_tool の機能を直接インポート可能に
from .list_tool import html_to_heroes,make_meta_list

# print_tool の機能を直接インポート可能に
from .print_tool import generate_meta_list_image

# categories_tool の機能を直接インポート可能に
from .categories_tool import load_hero_categories,add_hero_to_json,remove_hero_from_json

from .csv_tool import save_heroes_to_csv,generate_pick_up_html