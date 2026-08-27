from app.models import Venue
from app.extensions import db


VENUES = [
    {"name": "Wankhede Stadium", "city": "Mumbai", "country": "India", "lat": 18.9388, "lon": 72.8258, "pitch": "dry", "bat1": 55.0, "bat2": 45.0, "high": "387/5", "low": "112/10", "avg": 265.0},
    {"name": "Eden Gardens", "city": "Kolkata", "country": "India", "lat": 22.5646, "lon": 88.3433, "pitch": "sporting", "bat1": 52.0, "bat2": 48.0, "high": "438/9", "low": "94/10", "avg": 272.0},
    {"name": "M. A. Chidambaram Stadium", "city": "Chennai", "country": "India", "lat": 13.0629, "lon": 80.2792, "pitch": "dry", "bat1": 58.0, "bat2": 42.0, "high": "375/5", "low": "106/10", "avg": 258.0},
    {"name": "M. Chinnaswamy Stadium", "city": "Bengaluru", "country": "India", "lat": 12.9788, "lon": 77.5996, "pitch": "sporting", "bat1": 50.0, "bat2": 50.0, "high": "412/6", "low": "105/10", "avg": 268.0},
    {"name": "Rajiv Gandhi Intl Cricket Stadium", "city": "Hyderabad", "country": "India", "lat": 17.4065, "lon": 78.5507, "pitch": "dry", "bat1": 54.0, "bat2": 46.0, "high": "362/5", "low": "118/10", "avg": 260.0},
    {"name": "Arun Jaitley Stadium", "city": "Delhi", "country": "India", "lat": 28.6376, "lon": 77.2433, "pitch": "dry", "bat1": 56.0, "bat2": 44.0, "high": "389/4", "low": "101/10", "avg": 255.0},
    {"name": "Narendra Modi Stadium", "city": "Ahmedabad", "country": "India", "lat": 23.0916, "lon": 72.5967, "pitch": "dry", "bat1": 53.0, "bat2": 47.0, "high": "365/5", "low": "115/10", "avg": 262.0},
    {"name": "Green Park Stadium", "city": "Kanpur", "country": "India", "lat": 26.4592, "lon": 80.3457, "pitch": "sporting", "bat1": 51.0, "bat2": 49.0, "high": "347/5", "low": "108/10", "avg": 250.0},
    {"name": "Sawai Mansingh Stadium", "city": "Jaipur", "country": "India", "lat": 26.8930, "lon": 75.8075, "pitch": "dry", "bat1": 57.0, "bat2": 43.0, "high": "207/5", "low": "110/10", "avg": 240.0},
    {"name": "Lord's Cricket Ground", "city": "London", "country": "England", "lat": 51.5299, "lon": -0.1721, "pitch": "green", "bat1": 48.0, "bat2": 52.0, "high": "652/7d", "low": "45/10", "avg": 305.0},
    {"name": "The Oval", "city": "London", "country": "England", "lat": 51.4816, "lon": -0.0901, "pitch": "sporting", "bat1": 49.0, "bat2": 51.0, "high": "707/3d", "low": "44/10", "avg": 310.0},
    {"name": "Edgbaston Cricket Ground", "city": "Birmingham", "country": "England", "lat": 52.4559, "lon": -1.9174, "pitch": "sporting", "bat1": 47.0, "bat2": 53.0, "high": "594/5d", "low": "58/10", "avg": 298.0},
    {"name": "Headingley Cricket Ground", "city": "Leeds", "country": "England", "lat": 53.8168, "lon": -1.5835, "pitch": "green", "bat1": 46.0, "bat2": 54.0, "high": "653/4d", "low": "51/10", "avg": 302.0},
    {"name": "Old Trafford Cricket Ground", "city": "Manchester", "country": "England", "lat": 53.4631, "lon": -2.2914, "pitch": "sporting", "bat1": 50.0, "bat2": 50.0, "high": "672/8d", "low": "55/10", "avg": 308.0},
    {"name": "Melbourne Cricket Ground", "city": "Melbourne", "country": "Australia", "lat": -37.8205, "lon": 144.9834, "pitch": "sporting", "bat1": 52.0, "bat2": 48.0, "high": "624/8d", "low": "60/10", "avg": 315.0},
    {"name": "Sydney Cricket Ground", "city": "Sydney", "country": "Australia", "lat": -33.8610, "lon": 151.2249, "pitch": "sporting", "bat1": 53.0, "bat2": 47.0, "high": "707/5d", "low": "47/10", "avg": 320.0},
    {"name": "The Gabba", "city": "Brisbane", "country": "Australia", "lat": -27.4828, "lon": 153.0389, "pitch": "sporting", "bat1": 54.0, "bat2": 46.0, "high": "582/7d", "low": "58/10", "avg": 310.0},
    {"name": "Perth Stadium", "city": "Perth", "country": "Australia", "lat": -31.9442, "lon": 115.8606, "pitch": "sporting", "bat1": 51.0, "bat2": 49.0, "high": "549/9d", "low": "55/10", "avg": 295.0},
    {"name": "Adelaide Oval", "city": "Adelaide", "country": "Australia", "lat": -34.8964, "lon": 138.5951, "pitch": "sporting", "bat1": 50.0, "bat2": 50.0, "high": "674/8d", "low": "52/10", "avg": 305.0},
    {"name": "Newlands Cricket Ground", "city": "Cape Town", "country": "South Africa", "lat": -33.9299, "lon": 18.4547, "pitch": "green", "bat1": 47.0, "bat2": 53.0, "high": "651/7d", "low": "49/10", "avg": 295.0},
    {"name": "Wanderers Stadium", "city": "Johannesburg", "country": "South Africa", "lat": -26.1733, "lon": 28.0039, "pitch": "sporting", "bat1": 48.0, "bat2": 52.0, "high": "682/5d", "low": "53/10", "avg": 300.0},
    {"name": "Kensington Oval", "city": "Bridgetown", "country": "West Indies", "lat": 13.1043, "lon": -59.6368, "pitch": "sporting", "bat1": 49.0, "bat2": 51.0, "high": "790/3d", "low": "56/10", "avg": 310.0},
    {"name": "Sabina Park", "city": "Kingston", "country": "West Indies", "lat": 18.0027, "lon": -76.7828, "pitch": "sporting", "bat1": 50.0, "bat2": 50.0, "high": "629/9d", "low": "51/10", "avg": 298.0},
    {"name": "Galle International Stadium", "city": "Galle", "country": "Sri Lanka", "lat": 6.0566, "lon": 80.2210, "pitch": "dry", "bat1": 55.0, "bat2": 45.0, "high": "638/8d", "low": "67/10", "avg": 290.0},
    {"name": "Basin Reserve", "city": "Wellington", "country": "New Zealand", "lat": -41.3083, "lon": 174.7701, "pitch": "green", "bat1": 45.0, "bat2": 55.0, "high": "680/8d", "low": "42/10", "avg": 285.0},
    {"name": "Hagley Oval", "city": "Christchurch", "country": "New Zealand", "lat": -43.5350, "lon": 172.5854, "pitch": "green", "bat1": 46.0, "bat2": 54.0, "high": "671/6d", "low": "46/10", "avg": 290.0},
    {"name": "Sharjah Cricket Stadium", "city": "Sharjah", "country": "UAE", "lat": 25.3253, "lon": 55.4236, "pitch": "dry", "bat1": 53.0, "bat2": 47.0, "high": "364/5", "low": "102/10", "avg": 248.0},
    {"name": "Dubai International Cricket Stadium", "city": "Dubai", "country": "UAE", "lat": 25.0464, "lon": 55.2165, "pitch": "dry", "bat1": 52.0, "bat2": 48.0, "high": "355/5", "low": "99/10", "avg": 245.0},
    {"name": "Sher-e-Bangla National Cricket Stadium", "city": "Dhaka", "country": "Bangladesh", "lat": 23.7950, "lon": 90.3430, "pitch": "dry", "bat1": 55.0, "bat2": 45.0, "high": "556/8d", "low": "82/10", "avg": 285.0},
    {"name": "Gaddafi Stadium", "city": "Lahore", "country": "Pakistan", "lat": 31.5133, "lon": 74.3456, "pitch": "dry", "bat1": 54.0, "bat2": 46.0, "high": "628/8d", "low": "100/10", "avg": 295.0},
]


def seed_venues():
    count = 0
    for v in VENUES:
        existing = Venue.query.filter_by(name=v["name"], city=v["city"]).first()
        if existing:
            continue
        venue = Venue(
            name=v["name"],
            city=v["city"],
            country=v["country"],
            latitude=v["lat"],
            longitude=v["lon"],
            pitch_type=v["pitch"],
            batting_first_win_pct=v["bat1"],
            batting_second_win_pct=v["bat2"],
            highest_score=v["high"],
            lowest_score=v["low"],
            avg_score=v["avg"],
        )
        db.session.add(venue)
        count += 1
    db.session.commit()
    return count
