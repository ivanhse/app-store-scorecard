#!/usr/bin/env python3
"""Batch-evaluate 500 MORE app ideas through the App Store Scorecard."""

import json
import time
import sys
from itunes_api import search_apps, analyze_competition

KEYWORDS = [
    # ---- NICHE HEALTH (25) ----
    "lymphedema tracker", "ibs symptom diary", "endometriosis tracker",
    "fibromyalgia symptom log", "gout attack tracker", "asthma action plan app",
    "cpap tracker app", "dialysis schedule app", "insulin dose calculator",
    "physical therapy exercises", "rotator cuff exercises", "knee rehab exercises",
    "hip flexor stretches app", "neck pain exercises app", "sciatica relief exercises",
    "carpal tunnel exercises", "bunion exercises app", "frozen shoulder exercises",
    "tennis elbow exercises", "achilles tendon rehab", "shin splint recovery",
    "concussion recovery tracker", "blood oxygen tracker", "heart rate zones trainer",
    "resting heart rate log",

    # ---- TRADES & BLUE COLLAR (25) ----
    "electrician formulas app", "plumber pipe sizing", "hvac duct calculator",
    "welding rod selector", "sheet metal calculator", "scaffolding calculator",
    "gravel calculator app", "asphalt calculator", "drywall estimator app",
    "insulation calculator", "rebar calculator app", "soil calculator app",
    "paver calculator app", "fence calculator app", "deck board calculator",
    "stair stringer calculator", "crown molding angle calc", "wire gauge calculator",
    "breaker size calculator", "conduit fill calculator", "voltage drop calculator",
    "amp to watt converter", "torque converter calculator", "hydraulic calculator app",
    "pneumatic calculator app",

    # ---- PET NICHE (20) ----
    "puppy potty training", "dog anxiety app", "cat litter tracker",
    "aquarium water tester", "betta fish care guide", "hamster care guide",
    "guinea pig care app", "rabbit care tracker", "parrot training app",
    "chicken coop planner", "goat health tracker", "livestock weight estimator",
    "horse hoof tracker", "horse feeding calculator", "dog raw diet calculator",
    "cat food calculator", "pet insurance compare", "lost pet finder app",
    "pet adoption search", "dog age calculator",

    # ---- OUTDOOR ADVENTURE (25) ----
    "mushroom foraging guide", "wild plant identifier", "edible plant guide",
    "survival skills app", "knot tying guide app", "compass navigation app",
    "celestial navigation app", "weather radio app", "avalanche safety app",
    "river flow tracker", "tide prediction app", "fishing knots guide",
    "fly tying patterns app", "hunting season calendar", "deer call app",
    "duck call app", "turkey call app", "trail camera viewer",
    "tree identification app", "bird call identifier", "insect identifier app",
    "snake identification app", "mineral identification", "fossil identifier app",
    "cloud identification app",

    # ---- MUSIC & AUDIO (20) ----
    "chord progression generator", "songwriting app", "lyric writing app",
    "music sight reading app", "ear training app", "pitch pipe app",
    "drum machine app", "bass tuner app", "mandolin tuner app",
    "banjo tuner app", "harmonica key finder", "capo chart app",
    "music interval trainer", "rhythm trainer app", "music scales app",
    "sheet music reader app", "audio recorder hq app", "voice recorder notes",
    "podcast recording app", "sound level meter pro",

    # ---- COOKING DEEP NICHE (20) ----
    "air fryer recipes app", "instant pot timer app", "sous vide calculator",
    "bread proofing timer", "cheese making guide", "home canning guide app",
    "dehydrator recipes app", "jerky making guide", "hot sauce recipe app",
    "pickle recipe app", "jam making guide app", "kombucha brewing tracker",
    "mead brewing calculator", "wine making guide app", "cider making app",
    "whiskey tasting notes", "coffee roasting log", "tea brewing timer",
    "matcha preparation guide", "cold brew calculator",

    # ---- STUDENT LIFE (20) ----
    "class schedule planner", "homework tracker app", "school bus tracker",
    "college comparison app", "scholarship finder app", "student loan calculator",
    "textbook price compare", "study group organizer", "lab notebook app",
    "research paper organizer", "thesis tracker app", "exam countdown timer",
    "class notes organizer", "professor rating app", "campus map app",
    "dorm room planner", "roommate finder app", "meal plan tracker college",
    "internship tracker app", "resume builder app",

    # ---- ELDERLY CARE (15) ----
    "blood pressure diary", "glucose diary app", "joint pain tracker",
    "arthritis exercise app", "osteoporosis exercises", "balance exercises senior",
    "brain training seniors", "large clock app", "medication interaction checker",
    "caregiver schedule app", "dementia activity app", "hearing aid app",
    "vision magnifier app", "emergency medical info", "senior fitness tracker",

    # ---- PREGNANCY & BABY (20) ----
    "due date calculator app", "kick counter app", "baby name meaning app",
    "nursery design planner", "baby registry checklist", "postpartum recovery app",
    "breastmilk storage tracker", "pumping schedule app", "formula feeding tracker",
    "baby solid food tracker", "toddler meal ideas", "toddler activity planner",
    "baby development tracker", "baby photo milestone", "diaper rash guide",
    "colic relief guide app", "baby sign language app", "lullaby music app",
    "white noise baby app", "baby bath temperature",

    # ---- FINANCIAL PLANNING (20) ----
    "compound interest calculator", "retirement calculator app", "fire calculator app",
    "emergency fund tracker", "sinking fund tracker", "paycheck budget app",
    "hourly wage calculator", "overtime calculator app", "commission calculator app",
    "sales tax calculator", "import duty calculator", "vat calculator app",
    "profit margin calculator", "break even calculator", "roi calculator app",
    "stock option calculator", "capital gains calculator", "estate planning app",
    "charitable giving tracker", "tithe calculator app",

    # ---- HOME IMPROVEMENT (20) ----
    "paint quantity calculator", "wallpaper calculator app", "flooring calculator app",
    "kitchen layout planner", "bathroom remodel planner", "closet organizer planner",
    "garage organizer app", "shed building plans", "pool maintenance tracker",
    "hot tub maintenance app", "septic tank tracker", "water heater timer",
    "smart thermostat scheduler", "sprinkler schedule app", "gutter cleaning reminder",
    "chimney cleaning tracker", "radon testing reminder", "mold inspection guide",
    "home security planner", "doorbell camera viewer",

    # ---- FASHION & BEAUTY (15) ----
    "outfit planner app", "wardrobe organizer app", "skin care routine app",
    "hair care routine app", "nail art ideas app", "makeup shade finder",
    "perfume collection app", "jewelry organizer app", "shoe collection tracker",
    "thrift fashion app", "capsule wardrobe planner", "color season analyzer",
    "body measurement log", "plastic surgery research", "tattoo aftercare guide",

    # ---- LANGUAGE & CULTURE (15) ----
    "asl dictionary app", "braille learning app", "morse code trainer app",
    "phonetic alphabet app", "language exchange app", "dialect quiz app",
    "etymology dictionary app", "rhyming dictionary app", "idiom dictionary app",
    "slang dictionary app", "name pronunciation app", "country facts app",
    "flag quiz app", "capital cities quiz", "world clock app",

    # ---- GAMES & PUZZLES (20) ----
    "rubik cube solver app", "sudoku generator app", "crossword maker app",
    "word search creator", "jigsaw puzzle app", "brain teaser app",
    "logic puzzle app", "math puzzle app", "trivia quiz maker",
    "card game scorer", "board game timer", "board game rules app",
    "dnd dice roller app", "dnd character sheet app", "magic the gathering life",
    "poker odds calculator", "blackjack strategy app", "chess opening trainer",
    "chess endgame trainer", "go game app",

    # ---- EVENT PLANNING (15) ----
    "seating chart planner", "event budget tracker", "guest list manager",
    "invitation maker app", "photo booth app", "wedding countdown timer",
    "bachelor party planner", "baby shower planner", "birthday party planner",
    "reunion planner app", "funeral planning app", "memorial tribute app",
    "graduation party planner", "holiday party planner", "potluck organizer app",

    # ---- TRANSPORTATION (15) ----
    "flight delay predictor", "airline seat picker", "train schedule app",
    "bus route planner app", "ferry schedule app", "bike route planner",
    "scooter rental finder", "car rental compare app", "rideshare price compare",
    "parking meter timer", "toll calculator app", "fuel price tracker",
    "electric car charger map", "car insurance compare", "roadside assistance app",

    # ---- REAL ESTATE DEEP (15) ----
    "land area calculator", "plot size calculator", "property line finder",
    "home value estimator app", "comparable sales finder", "cap rate calculator",
    "cash flow calculator rental", "flip profit calculator", "wholesale deal analyzer",
    "airbnb profit calculator", "vacancy rate tracker", "tenant communication app",
    "rent collection app", "lease renewal reminder", "property inspection app",

    # ---- WELLNESS & ALTERNATIVE (15) ----
    "acupressure point guide", "reflexology chart app", "essential oil guide app",
    "aromatherapy blends app", "herb identification app", "herbal remedy guide",
    "homeopathy guide app", "ayurveda dosha quiz", "traditional chinese medicine",
    "reiki practice timer", "sound healing app", "singing bowl app",
    "binaural beats app", "solfeggio frequency app", "grounding exercises app",

    # ---- WRITING & CREATIVITY (15) ----
    "writing prompt generator", "character name generator", "plot generator app",
    "word count tracker app", "screenplay formatter app", "poetry writing app",
    "haiku generator app", "journal prompt app", "dream journal app",
    "bullet journal app", "mood board maker app", "vision board app",
    "gratitude jar app", "bucket list app", "goal tracker app",

    # ---- COMMUNITY & LOCAL (15) ----
    "neighborhood watch app", "local event finder app", "garage sale finder app",
    "buy nothing group app", "community garden app", "volunteer finder app",
    "blood donation finder", "food bank locator", "shelter finder app",
    "free wifi finder app", "public restroom finder", "playground finder app",
    "dog friendly places app", "handicap parking finder", "electric outlet finder",

    # ---- SCIENCE & ENGINEERING (15) ----
    "unit conversion pro app", "scientific calculator pro", "statistics calculator app",
    "matrix calculator app", "graphing calculator app", "chemical equation balancer",
    "molecular weight calculator", "dilution calculator app", "ph calculator app",
    "ohms law calculator", "transistor calculator", "led resistor calculator",
    "3d printer calculator", "filament usage calculator", "laser power calculator",

    # ---- SEASONAL & HOLIDAY (15) ----
    "christmas countdown app", "advent calendar app", "halloween costume ideas",
    "pumpkin carving guide", "easter egg ideas app", "valentines gift ideas",
    "mothers day gift ideas", "fathers day gift ideas", "thanksgiving menu planner",
    "new years resolution app", "tax season checklist", "spring cleaning checklist",
    "back to school checklist", "summer bucket list app", "winter preparation list",

    # ---- MISC UTILITY (20) ----
    "random number generator", "stopwatch app pro", "countdown timer pro",
    "world clock widget", "alarm clock app", "flashlight app pro",
    "ruler measurement app", "protractor angle app", "spirit level pro app",
    "sound frequency app", "vibration meter app", "emf detector app",
    "barcode generator app", "wifi password finder", "speed test app",
    "data usage monitor", "battery health checker", "storage cleaner app",
    "clipboard history app", "text to speech app",

    # ---- ADDITIONAL UNIQUE (25) ----
    "carbon offset calculator", "water quality tester", "air quality monitor app",
    "light pollution map", "dark sky finder app", "iss tracker app",
    "satellite tracker app", "ham radio logbook", "shortwave radio app",
    "police scanner app", "flight radar app", "ship tracker app",
    "earthquake monitor app", "volcano tracker app", "wildfire tracker app",
    "hurricane tracker app", "tornado tracker app", "flood alert app",
    "air raid siren app", "geiger counter app", "decibel meter pro",
    "frequency analyzer app", "spectrum analyzer app", "signal generator app",
    "white noise generator pro",

    # ---- FILL TO 500 (55) ----
    "cigar humidor tracker", "wine cellar inventory", "whiskey collection app",
    "craft beer log app", "cocktail shaker app", "smoothie builder app",
    "juice recipe app", "meal macro calculator", "carb counter app",
    "sodium tracker app", "fiber tracker app", "iron intake tracker",
    "calcium tracker app", "hydration reminder app", "electrolyte calculator",
    "sunscreen reminder app", "skincare ingredient checker", "food additive scanner",
    "pesticide residue guide", "organic food finder",
    "tiny house planner", "van life checklist", "rv maintenance tracker",
    "boat maintenance log", "kayak launch finder", "ski wax guide app",
    "snowboard tuning guide", "surfboard fin guide", "wetsuit thickness guide",
    "hiking gear checklist", "backpacking meal planner", "trail mix calculator",
    "camping checklist app", "campfire recipe app", "dutch oven recipe app",
    "cast iron care guide", "knife sharpening guide", "axe throwing scorer",
    "dart scoring app", "pool billiards scorer", "table tennis scorer",
    "badminton score tracker", "volleyball score app", "handball score tracker",
    "lacrosse stat tracker", "field hockey stats app", "water polo score app",
    "rowing split calculator", "cycling power calculator", "running pace calculator",
    "triathlon planner app", "marathon nutrition plan", "ultra running tracker",
    "hiking altitude tracker", "strava alternative app",
]

assert len(KEYWORDS) == 500, f"Expected 500 keywords, got {len(KEYWORDS)}"


def score_opportunity(analysis):
    opp = analysis.get("opportunity", "")
    base = {
        "GREAT OPPORTUNITY": 90,
        "GOOD OPPORTUNITY": 70,
        "COMPETITIVE — differentiate to win": 40,
        "SMALL NICHE — low risk, low reward": 30,
        "OVERSUPPLIED — strong apps, limited demand": 15,
        "AVOID — dominated market": 5,
    }.get(opp, 20)

    bonus = 0
    if analysis.get("stale_apps", 0) >= 3:
        bonus += 5
    if analysis.get("low_rated_apps", 0) >= 3:
        bonus += 5
    if analysis.get("avg_rating_count", 0) < 1000:
        bonus += 5
    if analysis.get("demand_level") == "VERY HIGH":
        bonus += 5
    elif analysis.get("demand_level") == "HIGH":
        bonus += 3
    gini = analysis.get("concentration_index")
    if gini is not None and gini < 0.4:
        bonus += 3
    weak = analysis.get("weak_apps_in_top25", 0)
    total = analysis.get("total_results", 1)
    if total > 0 and weak / max(total, 1) > 0.5:
        bonus += 3

    return base + bonus


def main():
    results = []
    total = len(KEYWORDS)

    print(f"Evaluating {total} app ideas (batch 2)...\n", file=sys.stderr)

    for i, kw in enumerate(KEYWORDS):
        print(f"[{i+1}/{total}] {kw}...", file=sys.stderr, end=" ", flush=True)
        try:
            apps = search_apps(kw, country="us", limit=25)
            analysis = analyze_competition(apps)
            sc = score_opportunity(analysis)
            results.append({
                "keyword": kw,
                "score": sc,
                "opportunity": analysis.get("opportunity", "?"),
                "demand_level": analysis.get("demand_level", "?"),
                "supply_level": analysis.get("supply_level", "?"),
                "total_ratings_all": analysis.get("total_ratings_all", 0),
                "avg_rating_count": analysis.get("avg_rating_count", 0),
                "avg_star_rating": analysis.get("avg_star_rating", 0),
                "stale_apps": analysis.get("stale_apps", 0),
                "low_rated_apps": analysis.get("low_rated_apps", 0),
                "weak_apps_in_top25": analysis.get("weak_apps_in_top25", 0),
                "mature_apps_pct": analysis.get("mature_apps_pct"),
                "concentration_index": analysis.get("concentration_index"),
                "top_3_apps": [
                    {"name": a["name"], "ratings": a["rating_count"], "stars": a["star_rating"]}
                    for a in apps[:3]
                ],
            })
            print(f"score={sc} ({analysis.get('opportunity', '?')})", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            results.append({"keyword": kw, "score": 0, "error": str(e)})

        if i < total - 1:
            time.sleep(3)

    results.sort(key=lambda r: r.get("score", 0), reverse=True)

    with open("batch_results_2.json", "w") as f:
        json.dump(results, f, indent=2)

    # Merge with batch 1
    batch1 = []
    try:
        with open("batch_results.json") as f:
            batch1 = json.load(f)
    except FileNotFoundError:
        pass

    existing_keywords = {r["keyword"].lower() for r in batch1}
    new_results = [r for r in results if r["keyword"].lower() not in existing_keywords]
    merged = batch1 + new_results
    merged.sort(key=lambda r: r.get("score", 0), reverse=True)

    with open("batch_results.json", "w") as f:
        json.dump(merged, f, indent=2)

    print(f"\nDone! {len(new_results)} new + {len(batch1)} existing = {len(merged)} total in batch_results.json", file=sys.stderr)


if __name__ == "__main__":
    main()
