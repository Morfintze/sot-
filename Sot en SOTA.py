import requests
from bs4 import BeautifulSoup
import re
import unicodedata
import streamlit as st

# --------------------------
# Helpers
# --------------------------
def normalize_str(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf8')
    s = s.lower()
    s = re.sub(r'[^a-z0-9]', '', s)
    return s

def team_matches(candidate, team_input):
    n_candidate = normalize_str(candidate)
    n_team = normalize_str(team_input)
    return n_team in n_candidate or n_candidate in n_team

# --------------------------
# Hoofd functie
# --------------------------
def get_team_stats(teamnaam):
    search_url = f"https://fbref.com/en/search/search.fcgi?search={teamnaam}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    resultaten = soup.find_all("a", href=True, string=lambda t: t and team_matches(t, teamnaam))
    team_url = None
    for resultaat in resultaten:
        candidate_url = "https://fbref.com" + resultaat["href"]
        if ("/squads/" in candidate_url or "/teams/" in candidate_url) and "/players/" not in candidate_url:
            team_url = candidate_url
            break
    
    if not team_url:
        st.error(f"❌ Geen teampagina gevonden voor {teamnaam}.")
        return
    
    st.markdown(f"✅ **Team gevonden:** [{team_url}]({team_url})")

    try:
        response = requests.get(team_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # SoTA & MP
        sota_td = soup.find("td", {"data-stat": "gk_shots_on_target_against"})
        mp_td = soup.find("td", {"data-stat": "gk_games"})
        sota_value = float(sota_td.text.strip()) if sota_td and sota_td.text.strip() else None
        mp_value = float(mp_td.text.strip()) if mp_td and mp_td.text.strip() else None

        if sota_value is not None and mp_value is not None:
            ratio = sota_value / mp_value
            st.write(f"📉 **SoTA / MP ratio:** {ratio:.2f}")
        else:
            st.warning("⚠️ Kan de SoTA / MP ratio niet berekenen.")

        # Laatste 5 wedstrijden
        results = [td.text.strip() for td in soup.find_all("td", {"data-stat": "result"})]
        results = [x for x in results if x][-5:]
        points = sum(3 if r == "W" else 1 if r == "D" else 0 for r in results)
        st.write(f"📅 **Laatste 5 wedstrijden:** {' '.join(results)}")
        st.write(f"⭐ **Punten laatste 5 wedstrijden:** {points}")

        # Spelers info
        spelers_url = team_url + "/players/"
        response = requests.get(spelers_url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        
        spelers_info = {}
        debug_data = {}
        
        # Mn/MP
        for speler in soup.find_all("tr"):
            speler_naam_tag = speler.find("a", href=True)
            mn_mp_td = speler.find("td", {"data-stat": "minutes_per_game"})
            if speler_naam_tag and mn_mp_td:
                speler_naam = speler_naam_tag.get_text(strip=True)
                try:
                    debug_data[speler_naam] = float(mn_mp_td.text.strip())
                except ValueError:
                    pass

        # SOT/90 en SH/90
        for speler in soup.find_all("tr"):
            speler_naam_tag = speler.find("a", href=True)
            sot_90_td = speler.find("td", {"data-stat": "shots_on_target_per90"})
            sh_90_td = speler.find("td", {"data-stat": "shots_per90"})
            if speler_naam_tag:
                speler_naam = speler_naam_tag.get_text(strip=True)
                mn_mp = debug_data.get(speler_naam, None)
                if sot_90_td:
                    try:
                        spelers_info.setdefault(speler_naam, {})["sot_90"] = float(sot_90_td.text.strip())
                        spelers_info[speler_naam]["mn_mp"] = mn_mp
                    except ValueError:
                        pass
                if sh_90_td:
                    try:
                        spelers_info.setdefault(speler_naam, {})["sh_90"] = float(sh_90_td.text.strip())
                        spelers_info[speler_naam]["mn_mp"] = mn_mp
                    except ValueError:
                        pass

        # Sorteren en tonen
        sorted_sot = sorted(spelers_info.items(), key=lambda x: x[1].get("sot_90", 0), reverse=True)[:5]
        sorted_sh = sorted(spelers_info.items(), key=lambda x: x[1].get("sh_90", 0), reverse=True)[:5]

        if sorted_sot:
            st.subheader("🏆 Top 5 SOT/90")
            sot_df = [{"Naam": naam, "SOT/90": stats["sot_90"], "Mn/MP": stats["mn_mp"]} for naam, stats in sorted_sot]
            st.table(sot_df)
        
        if sorted_sh:
            st.subheader("🎯 Top 5 SH/90")
            sh_df = [{"Naam": naam, "SH/90": stats["sh_90"], "Mn/MP": stats["mn_mp"]} for naam, stats in sorted_sh]
            st.table(sh_df)
    
    except Exception as e:
        st.error(f"⚠️ Fout bij ophalen gegevens: {e}")

# --------------------------
# Streamlit UI
# --------------------------
st.title("FBref Team Statistieken 📊")
teamnaam = st.text_input("Voer teamnaam in:")

if teamnaam:
    get_team_stats(teamnaam)
