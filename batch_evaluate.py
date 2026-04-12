#!/usr/bin/env python3
"""Batch-evaluate 500 app ideas through the App Store Scorecard."""

import json
import time
import sys
from itunes_api import search_apps, analyze_competition

KEYWORDS = [
    # ---- HEALTH & FITNESS (30) ----
    "posture corrector app", "water intake tracker", "intermittent fasting timer",
    "wrist pain exercises", "pelvic floor trainer", "eye strain relief app",
    "cold plunge timer", "sauna tracker", "grip strength trainer",
    "sleep noise generator", "snoring tracker", "teeth grinding tracker",
    "vitamin tracker app", "allergy symptom tracker", "blood pressure log",
    "glucose monitor app", "migraine diary app", "skin condition tracker",
    "hair loss tracker", "supplement reminder app", "body measurement tracker",
    "flexibility training app", "desk stretch reminder", "plantar fasciitis exercises",
    "TMJ exercises app", "scoliosis exercises app", "vertigo exercises app",
    "tinnitus relief app", "dry eye tracker", "jaw exercises app",

    # ---- PERSONAL FINANCE (25) ----
    "subscription tracker app", "tip calculator app", "debt payoff planner",
    "savings goal tracker", "rent split calculator", "cash envelope budget",
    "net worth tracker", "side hustle income tracker", "tax deduction tracker",
    "receipt scanner app", "warranty tracker app", "price comparison scanner",
    "garage sale pricer", "coin collection value", "bill negotiator app",
    "credit score simulator", "investment fee calculator", "dividend tracker app",
    "crypto tax calculator", "freelance invoice app", "expense report app",
    "allowance tracker kids", "wedding budget planner", "car cost calculator",
    "utility bill tracker",

    # ---- PRODUCTIVITY (30) ----
    "meeting cost calculator", "email template app", "voice memo transcriber",
    "clipboard manager app", "screen time limiter", "pomodoro timer app",
    "habit streak tracker", "daily journal app", "goal setting app",
    "decision maker app", "random wheel spinner", "checklist app simple",
    "todo list minimal", "time blocking app", "deep work timer",
    "morning routine app", "evening routine app", "weekly planner app",
    "project milestone tracker", "reading list tracker", "bookmark manager app",
    "password generator app", "unit converter app", "qr code scanner app",
    "document scanner app", "text expander app", "batch image resizer",
    "file organizer app", "pdf editor mobile", "note taking app simple",

    # ---- FOOD & COOKING (25) ----
    "meal prep planner", "leftover recipe finder", "pantry inventory app",
    "grocery list app", "recipe scaler app", "cooking timer multiple",
    "meat temperature guide", "sourdough starter tracker", "fermentation tracker",
    "cocktail recipe app", "wine pairing app", "beer brewing tracker",
    "coffee brew timer", "spice substitution app", "baking conversion app",
    "food expiration tracker", "restaurant tip splitter", "diet meal planner",
    "calorie counter simple", "protein tracker app", "smoothie recipe app",
    "baby food tracker", "school lunch planner", "freezer inventory app",
    "bbq smoker temperature",

    # ---- PARENTING & FAMILY (20) ----
    "baby sleep tracker", "breastfeeding tracker", "diaper change log",
    "baby milestone tracker", "kids chore chart app", "family calendar app",
    "co-parenting schedule", "baby name finder", "pregnancy week tracker",
    "contraction timer app", "potty training tracker", "kids allowance app",
    "family chore app", "screen time kids", "kids reward chart",
    "baby feeding schedule", "growth chart tracker", "vaccination tracker app",
    "school pickup reminder", "nanny cam viewer app",

    # ---- PET CARE (15) ----
    "dog walk tracker", "pet feeding schedule", "vet appointment reminder",
    "dog training app", "cat health tracker", "pet expense tracker",
    "dog breed identifier", "pet medication reminder", "fish tank monitor",
    "bird species identifier", "horse training log", "pet weight tracker",
    "dog park finder", "pet first aid app", "reptile care guide",

    # ---- HOME & GARDEN (20) ----
    "plant watering reminder", "home maintenance schedule", "paint color matcher",
    "furniture measurement app", "room layout planner", "lawn care schedule",
    "garden planting calendar", "compost tracker app", "weed identifier app",
    "indoor plant identifier", "home inventory app", "moving checklist app",
    "cleaning schedule app", "laundry care symbols", "stain removal guide app",
    "power outage tracker", "noise level meter app", "humidity monitor app",
    "home energy monitor", "smart home controller",

    # ---- AUTOMOTIVE (15) ----
    "car maintenance tracker", "gas mileage tracker", "parking spot finder",
    "oil change reminder", "tire pressure checker", "car wash finder",
    "road trip planner app", "speed limit alert app", "dash cam app",
    "car value estimator", "vin decoder app", "obd2 scanner app",
    "car mod tracker", "motorcycle maintenance log", "ev charging finder",

    # ---- MENTAL HEALTH & MINDFULNESS (20) ----
    "mood tracker app", "anxiety relief app", "breathing exercises app",
    "gratitude journal app", "affirmation app daily", "meditation timer simple",
    "therapy session notes", "anger management app", "stress level tracker",
    "self care checklist", "emotion wheel app", "cbt thought diary",
    "mindfulness bell app", "body scan meditation", "sleep meditation app",
    "panic attack helper", "sobriety counter app", "addiction recovery app",
    "grief support app", "loneliness support app",

    # ---- EDUCATION & LEARNING (20) ----
    "flashcard maker app", "speed reading trainer", "vocabulary builder app",
    "math practice app", "typing speed test", "sign language learning",
    "astronomy star map", "periodic table app", "geography quiz app",
    "history timeline app", "music theory app", "chess trainer app",
    "sudoku solver app", "crossword helper app", "language pronunciation app",
    "coding practice app", "study timer app", "gpa calculator app",
    "citation generator app", "study group finder",

    # ---- SOCIAL & COMMUNICATION (15) ----
    "icebreaker questions app", "group decision maker", "event planner app",
    "rsvp tracker app", "gift list tracker", "birthday reminder app",
    "contact backup app", "couple journal app", "long distance relationship",
    "neighbor communication app", "carpool coordinator app", "roommate expense splitter",
    "party game app", "truth or dare app", "would you rather app",

    # ---- TRAVEL (20) ----
    "packing list app", "travel budget tracker", "currency converter app",
    "flight tracker app", "hotel price compare", "travel journal app",
    "offline maps app", "language translator app", "timezone converter app",
    "travel itinerary planner", "airport lounge finder", "visa requirement checker",
    "travel insurance compare", "luggage tracker app", "jet lag calculator",
    "road trip gas calculator", "campsite finder app", "hiking trail tracker",
    "national park guide", "travel photo organizer",

    # ---- SPORTS & OUTDOOR (20) ----
    "golf score tracker", "fishing log app", "hunting journal app",
    "bowling score keeper", "tennis score tracker", "basketball stat tracker",
    "soccer formation app", "swimming lap counter", "rock climbing tracker",
    "kayak route planner", "ski resort tracker", "surf conditions app",
    "skateboard trick tracker", "archery score tracker", "marathon training plan",
    "yoga pose guide", "weightlifting log app", "calisthenics workout app",
    "pickleball score tracker", "disc golf tracker",

    # ---- CREATIVE & HOBBIES (25) ----
    "color palette generator", "drawing tutorial app", "pixel art maker",
    "knitting pattern counter", "crochet stitch counter", "sewing pattern app",
    "woodworking plans app", "3d printing slicer", "calligraphy practice app",
    "origami instructions app", "pottery glaze calculator", "candle making guide",
    "soap making calculator", "resin art guide", "jewelry making guide",
    "embroidery pattern app", "cross stitch pattern", "bead pattern maker",
    "model train layout", "rc car tuning app", "aquarium planner app",
    "terrarium guide app", "bonsai care guide", "mushroom identifier app",
    "rock identification app",

    # ---- REAL ESTATE & PROPERTY (15) ----
    "mortgage calculator app", "rent vs buy calculator", "home inspection checklist",
    "property tax estimator", "renovation cost estimator", "roi calculator rental",
    "tenant screening app", "lease agreement template", "move in checklist app",
    "utility setup checklist", "neighborhood safety app", "school district finder",
    "commute time calculator", "home appraisal estimate", "closing cost calculator",

    # ---- BUSINESS & FREELANCE (20) ----
    "business card scanner", "meeting notes app", "crm simple app",
    "invoice generator app", "time tracker freelance", "contract template app",
    "brand color picker", "social media scheduler", "hashtag generator app",
    "follower analytics app", "content calendar app", "email newsletter app",
    "customer feedback app", "appointment scheduler", "booking app simple",
    "inventory tracker small", "barcode scanner business", "shipping cost calculator",
    "business name generator", "logo maker app simple",

    # ---- NICHE PROFESSIONAL (20) ----
    "construction calculator", "electrician wire calculator", "plumbing pipe calculator",
    "hvac load calculator", "concrete calculator app", "roofing calculator app",
    "paint coverage calculator", "tile calculator app", "lumber calculator app",
    "welding settings guide", "cnc feed rate calculator", "machinist calculator app",
    "nurse shift tracker", "teacher grade book app", "bartender recipe app",
    "dj bpm counter app", "photographer shot list", "videographer shot list",
    "real estate showing tracker", "salon appointment app",

    # ---- SENIORS & ACCESSIBILITY (10) ----
    "large text magnifier", "pill reminder simple", "emergency contact app",
    "hearing test app", "fall detection app", "senior exercise app",
    "memory games seniors", "voice assistant senior", "simple phone launcher",
    "medical id app",

    # ---- SUSTAINABILITY & ECO (10) ----
    "carbon footprint tracker", "zero waste guide app", "recycling guide app",
    "ethical shopping scanner", "thrift store finder", "water usage tracker",
    "energy saving tips app", "sustainable recipe app", "eco product scanner",
    "plastic free alternatives",

    # ---- DATING & RELATIONSHIPS (10) ----
    "date idea generator", "relationship quiz app", "love language test",
    "couple games app", "date night planner", "anniversary reminder app",
    "conversation starters app", "couples budget app", "wedding planning app",
    "honeymoon planner app",

    # ---- WEATHER & NATURE (10) ----
    "rain alert app", "pollen count tracker", "uv index tracker app",
    "sunrise sunset times", "moon phase calendar", "tide chart app",
    "wind speed meter", "lightning tracker app", "earthquake alert app",
    "aurora forecast app",

    # ---- LEGAL & DOCUMENTS (10) ----
    "will maker simple app", "power of attorney template", "nda generator app",
    "small claims court guide", "tenant rights app", "lemon law guide app",
    "traffic ticket helper", "jury duty tracker", "notary finder app",
    "legal document scanner",

    # ---- FAITH & SPIRITUALITY (10) ----
    "daily bible verse app", "prayer tracker app", "quran reading app",
    "meditation mantra app", "tarot card reading app", "astrology chart app",
    "numerology calculator", "crystal guide app", "chakra meditation app",
    "daily devotional app",

    # ---- UNIQUE / EMERGING (30) ----
    "asmr sounds app", "white noise machine app", "lucid dream trainer",
    "sleep talk recorder", "time capsule app", "bucket list tracker",
    "random act of kindness", "compliment generator app", "debate timer app",
    "public speaking timer", "auction sniper tracker", "thrift flip tracker",
    "side project tracker", "startup idea validator", "microhabit tracker",
    "dopamine detox timer", "social media detox app", "news summary app",
    "ai photo enhancer app", "background remover app", "voice changer app",
    "sound frequency generator", "metal detector app", "ghost detector app",
    "level tool app", "compass app simple", "magnifying glass app",
    "morse code translator", "binary translator app", "wifi analyzer app",

    # ---- ADDITIONAL NICHE (20) ----
    "blood type diet app", "kegel exercise tracker", "height growth tracker",
    "face yoga exercises", "tongue tie exercises", "lymphatic drainage guide",
    "foam roller exercises", "resistance band workout", "balance board exercises",
    "hand grip trainer app", "speed cube timer app", "chess clock app",
    "dice roller app", "coin flip app", "scoreboard app simple",
    "shot clock timer", "referee whistle app", "sports bracket maker",
    "fantasy draft helper", "sports betting tracker",

    # ---- ADDITIONAL TO REACH 500 (35) ----
    "stutter therapy app", "colorblind test app", "blood donation tracker",
    "organ donor app", "first aid guide app", "cpr instructions app",
    "poison control guide", "sos emergency app", "disaster preparedness app",
    "evacuation route app", "ham radio frequency app", "weather station app",
    "barometric pressure app", "dew point calculator", "heat index calculator",
    "noise cancellation app", "tuning fork app", "metronome app simple",
    "drum pad app", "piano practice app", "guitar tuner app",
    "ukulele tuner app", "vocal warmup app", "rap rhyme finder app",
    "beat maker simple app", "vinyl record tracker", "book trading app",
    "stamp collection tracker", "trading card scanner", "lego set tracker",
    "funko pop tracker", "sneaker price tracker", "thrift haul tracker",
    "vintage clothing guide", "antique identifier app",
]

assert len(KEYWORDS) == 500, f"Expected 500 keywords, got {len(KEYWORDS)}"


def score_opportunity(analysis):
    """Numeric score: higher = better opportunity. Range roughly 0-100."""
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
    # Bonus for stale/low-quality competitors
    if analysis.get("stale_apps", 0) >= 3:
        bonus += 5
    if analysis.get("low_rated_apps", 0) >= 3:
        bonus += 5
    # Bonus for weak incumbents
    if analysis.get("avg_rating_count", 0) < 1000:
        bonus += 5
    # Bonus for high demand
    if analysis.get("demand_level") == "VERY HIGH":
        bonus += 5
    elif analysis.get("demand_level") == "HIGH":
        bonus += 3
    # Bonus for low concentration (fragmented market)
    gini = analysis.get("concentration_index")
    if gini is not None and gini < 0.4:
        bonus += 3
    # Bonus for lots of weak apps in results
    weak = analysis.get("weak_apps_in_top10", 0)
    total = analysis.get("total_results", 1)
    if total > 0 and weak / max(total, 1) > 0.5:
        bonus += 3

    return base + bonus


def main():
    results = []
    total = len(KEYWORDS)

    print(f"Evaluating {total} app ideas...\n", file=sys.stderr)

    for i, kw in enumerate(KEYWORDS):
        print(f"[{i+1}/{total}] {kw}...", file=sys.stderr, end=" ", flush=True)
        try:
            apps = search_apps(kw, country="us", limit=10)
            analysis = analyze_competition(apps)
            sc = score_opportunity(analysis)
            results.append({
                "keyword": kw,
                "score": sc,
                "opportunity": analysis.get("opportunity", "?"),
                "demand_level": analysis.get("demand_level", "?"),
                "supply_level": analysis.get("supply_level", "?"),
                "total_ratings_top10": analysis.get("total_ratings_top10", 0),
                "avg_rating_count": analysis.get("avg_rating_count", 0),
                "avg_star_rating": analysis.get("avg_star_rating", 0),
                "stale_apps": analysis.get("stale_apps", 0),
                "low_rated_apps": analysis.get("low_rated_apps", 0),
                "weak_apps_in_top10": analysis.get("weak_apps_in_top10", 0),
                "mature_apps_pct": analysis.get("mature_apps_pct"),
                "concentration_index": analysis.get("concentration_index"),
                "top_3_apps": [
                    {"name": a["name"], "ratings": a["rating_count"], "stars": a["star_rating"]}
                    for a in apps[:3]
                ],
                "top_10_names": [a["name"] for a in apps[:10]],
            })
            print(f"score={sc} ({analysis.get('opportunity', '?')})", file=sys.stderr)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            results.append({"keyword": kw, "score": 0, "error": str(e)})

        if i < total - 1:
            time.sleep(3)

    # Sort by score descending
    results.sort(key=lambda r: r.get("score", 0), reverse=True)

    # Save full results
    with open("batch_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone! Results saved to batch_results.json", file=sys.stderr)
    print(f"\n{'='*80}", file=sys.stderr)
    print(f"TOP 30 OPPORTUNITIES:", file=sys.stderr)
    print(f"{'='*80}", file=sys.stderr)
    for i, r in enumerate(results[:30], 1):
        print(f"{i:2}. [{r['score']:3}] {r['keyword']:<35} "
              f"Demand={r.get('demand_level','?'):<10} Supply={r.get('supply_level','?'):<10} "
              f"=> {r.get('opportunity','?')}", file=sys.stderr)


if __name__ == "__main__":
    main()
