###  計算本体
import math
def sigmoid(x,alpha,c):
    return 1 / (1 + math.exp(-alpha * (x - c)))
    
def calculate_score(data,average_win_rate,average_pick_rate,kw=20 ,ku=5, kb=75,alpha=2.0,c=1.5):
    win_rate = float(data["win_rate"].strip('%'))
    pick_rate = float(data["pick_rate"].strip('%'))
    ban_rate = float(data["ban_rate"].strip('%'))
    # 勝率基礎点
    diff = win_rate - average_win_rate    
    W = average_win_rate + kw * (math.exp(diff / 10) - 1)
    # 使用率補正
    pick_correction = ku * (sigmoid(pick_rate,alpha,c*average_pick_rate))
    # 禁止率加点
    B = kb * ban_rate/100
    #print(f"{W:.2f},{pick_correction:.2f},{B:.2f}")
    
    total_score = W + pick_correction + B
    baseline = 50 + ku * (sigmoid(average_pick_rate,alpha,c*average_pick_rate)) + kb * 0
    correction = 50 - baseline
    total_score += correction
    return total_score
    
def add_scores_to_heroes(heroes):
    ave_w_r = 50.00
    ave_p_r = 1/len(heroes) * 100
    for hero in heroes:
        hero['meta_score'] = calculate_score(hero,ave_w_r,ave_p_r)
    return heroes
    
def assign_tier(score):
    if score >= 60:
        return "S"
    elif score >= 55:
        return "A"
    elif score >= 50:
        return "B"
    elif score >= 45:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "E"

def add_tier_to_heroes(heroes):
    for hero in heroes:
        hero['tier'] = assign_tier(hero['meta_score'])
    return heroes
    
def add_info_to_heroes(heroes):
    heroes = add_scores_to_heroes(heroes)
    heroes = add_tier_to_heroes(heroes)
    
    return heroes