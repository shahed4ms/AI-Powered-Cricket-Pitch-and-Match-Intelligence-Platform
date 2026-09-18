from app import create_app
from app.extensions import db
from app.models import Venue, VenueFormatStats
from app.services import venue_service


def test_get_venue_stats_includes_all_format_comparisons():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        venue = Venue(name='Test Ground', city='Test City', country='Test Country')
        db.session.add(venue)
        db.session.flush()

        for fmt, avg, mx, mn in [
            ('T20', 170.2, 220, 120),
            ('ODI', 260.5, 310, 180),
            ('Test', 340.75, 450, 200),
        ]:
            db.session.add(VenueFormatStats(
                venue_id=venue.id,
                format=fmt,
                batting_first_matches=10,
                batting_first_wins=6,
                batting_first_win_pct=60.0,
                bowling_first_matches=10,
                bowling_first_wins=4,
                bowling_first_win_pct=40.0,
                innings_count=20,
                first_innings_count=10,
                second_innings_count=10,
                avg_first_innings_score=avg,
                max_first_innings_score=mx,
                min_first_innings_score=mn,
                avg_second_innings_score=avg - 10,
                max_second_innings_score=mx - 25,
                min_second_innings_score=mn - 15,
            ))

        db.session.commit()

        stats = venue_service.get_venue_stats(venue.id, 'T20')

        assert stats['selected_format'] == 'T20'
        assert set(stats['format_comparison'].keys()) == {'T20', 'ODI', 'Test'}
        assert stats['format_comparison']['T20']['scores']['first_innings']['average'] == 170.2
        assert stats['format_comparison']['ODI']['scores']['first_innings']['maximum'] == 310
        assert stats['format_comparison']['Test']['scores']['second_innings']['minimum'] == 185


def test_get_venue_stats_falls_back_to_available_format_when_selected_format_is_missing():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        venue = Venue(name='Fallback Ground', city='Fallback City', country='Test Country')
        db.session.add(venue)
        db.session.flush()

        for fmt, avg, mx, mn in [
            ('T20', 160.0, 220, 110),
            ('Test', 330.0, 440, 190),
        ]:
            db.session.add(VenueFormatStats(
                venue_id=venue.id,
                format=fmt,
                batting_first_matches=10,
                batting_first_wins=6,
                batting_first_win_pct=60.0,
                bowling_first_matches=10,
                bowling_first_wins=4,
                bowling_first_win_pct=40.0,
                innings_count=20,
                first_innings_count=10,
                second_innings_count=10,
                avg_first_innings_score=avg,
                max_first_innings_score=mx,
                min_first_innings_score=mn,
                avg_second_innings_score=avg - 10,
                max_second_innings_score=mx - 25,
                min_second_innings_score=mn - 15,
            ))

        db.session.commit()

        stats = venue_service.get_venue_stats(venue.id, 'ODI')

        assert stats['selected_format'] == 'T20'
        assert stats['historical']['scores']['first_innings']['average'] == 160.0
        assert stats['historical']['scores']['second_innings']['maximum'] == 195


def test_search_venues_prioritizes_stadiums_over_city_matches_for_city_queries():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        db.session.add_all([
            Venue(name='Chennai', city='Chennai', country='India'),
            Venue(name='M. A. Chidambaram Stadium', city='Chennai', country='India'),
            Venue(name='Chennai International Airport', city='Chennai', country='India'),
        ])
        db.session.commit()

        results = venue_service.search_venues('Chennai')
        names = [item['name'] for item in results]

        assert 'M. A. Chidambaram Stadium' in names
        assert names.index('M. A. Chidambaram Stadium') < names.index('Chennai')
        assert names[0] == 'M. A. Chidambaram Stadium'
