from hok_tools.categories_tool import get_heroes_by_tag

### データの前処理ブロック
def read_html_from_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    
    return html_content

def extract_hero_data(html_content):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    heroes = []
    hero_rows = soup.find_all('tr')

    for row in hero_rows:
        hero_data = {}
        hero_name_tag = row.find('div', class_='hero-intro-name')
        if hero_name_tag:
            hero_data['name'] = hero_name_tag.text.strip()
        
        # 勝率、使用率、禁止率の取得
        stats_tags = row.find_all('div', class_=['table-text table-normal-text', 'table-text table-trank-text'])

        if len(stats_tags) >= 4:
            hero_data['win_rate'] = stats_tags[1].text.strip()
            hero_data['pick_rate'] = stats_tags[2].text.strip()
            hero_data['ban_rate'] = stats_tags[3].text.strip()


        if hero_data:
            heroes.append(hero_data)

    return heroes
    
def html_to_heroes(file_path):
    html_content = read_html_from_file(file_path)
    heroes = extract_hero_data(html_content)
    
    return heroes
    
### リストを標準出力（デバッグ用）
def make_meta_list(roll,heroes):
    roll = get_heroes_by_tag(roll)
    roll_heroes = [hero for hero in heroes if hero['name'] in roll]
    roll_sorted = sorted(roll_heroes, key=lambda hero:hero['meta_score'], reverse=True)

    print("name:score -- w/p/b")
    for hero in roll_sorted:
        print(f"{hero['name']}:{hero['meta_score']:.2f} -- {hero['win_rate']}/{hero['pick_rate']}/{hero['ban_rate']}")