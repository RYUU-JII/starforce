from fastapi import APIRouter
from ..models.schemas import AuditQuery, SeasonContrastQuery
from ..core.audit_engine import (
    get_audit_db, filter_audit_data, calculate_stats,
    get_heatmap_stats, get_drift_stats, get_monthly_stats,
    get_event_comparison_stats, get_event_deception_index, get_event_dates,
    get_season_contrast_stats
)

router = APIRouter(prefix="/api/audit", tags=["audit"])

@router.get("/meta")
def get_audit_metadata():
    db = get_audit_db()
    events = sorted(list(set(r["_event"] for r in db)))
    stars = sorted(list(set(r["star"] for r in db)))
    dates = sorted(list(set(r["_date"] for r in db)))
    
    return {
        "events": events,
        "stars": stars,
        "dates": dates,
        "total_records": len(db)
    }

@router.post("/query")
def query_audit_data(q: AuditQuery):
    filtered, included, skipped, total = filter_audit_data(
        events=q.events,
        stars=q.stars,
        catch_ops=q.catch_ops,
        min_samples=q.min_samples
    )
    
    results = calculate_stats(filtered)
    
    return {
        "results": results,
        "count": len(results),
        "debug_info": {
            "db_size": total,
            "included": included,
            "skipped": skipped
        }
    }

@router.post("/bundle")
def get_audit_bundle(q: AuditQuery):
    """Fetch a consistent set of audit stats with the same filters."""
    filtered, included, skipped, total = filter_audit_data(
        events=q.events,
        stars=q.stars,
        catch_ops=q.catch_ops,
        min_samples=q.min_samples
    )

    results = calculate_stats(filtered)
    heatmap = get_heatmap_stats(filtered_db=filtered)
    drift = get_drift_stats(filtered_db=filtered)
    monthly = get_monthly_stats(filtered_db=filtered)
    event_dec = get_event_deception_index(filtered)
    season = get_season_contrast_stats(filtered_db=filtered)

    dates = sorted(list(set(r["date"] for r in heatmap)))
    stars = sorted(list(set(r["star"] for r in heatmap)))

    return {
        "query": {
            "results": results,
            "count": len(results),
            "debug_info": {
                "db_size": total,
                "included": included,
                "skipped": skipped
            }
        },
        "heatmap": {
            "data": heatmap,
            "dates": dates,
            "stars": stars
        },
        "drift": drift,
        "monthly": monthly,
        "eventDec": event_dec,
        "eventDates": get_event_dates(),
        "seasonContrast": season
    }

@router.get("/heatmap")
def get_heatmap_data():
    """Returns Z-score data grouped by (star, date) for heatmap visualization."""
    results = get_heatmap_stats()
    
    # Get unique sorted dates and stars for axes
    dates = sorted(list(set(r["date"] for r in results)))
    stars = sorted(list(set(r["star"] for r in results)))
    
    return {
        "data": results,
        "dates": dates,
        "stars": stars
    }

@router.get("/drift")
def get_drift_data():
    """Returns Z-score drift over time for Zero-sum Audit analysis."""
    results = get_drift_stats()
    return {"drift": results}

@router.get("/monthly")
def get_monthly_data():
    """Returns aggregated Z-score stats by month."""
    results = get_monthly_stats()
    return {"monthly": results}

@router.get("/event-comparison")
def get_event_comparison():
    """Comparison of Z-Scores between Event vs Non-Event periods."""
    return get_event_comparison_stats()

@router.post("/event-deception")
def get_event_deception(q: AuditQuery):
    """Calculate the Event Deception Index based on probability suppression with filters."""
    filtered, _, _, _ = filter_audit_data(
        events=q.events,
        stars=q.stars,
        catch_ops=q.catch_ops,
        min_samples=q.min_samples
    )
    return get_event_deception_index(filtered)

@router.get("/event-dates")
def get_event_dates_api():
    """Return map of dates to event names for chart overlays."""
    return {"dates": get_event_dates()}

@router.get("/season-contrast")
def get_season_contrast(split_date: str = None):
    """Compare [Peak Loan] vs [Off-peak Collection] seasons with optional split_date."""
    return get_season_contrast_stats(split_date=split_date)

@router.post("/season-contrast")
def post_season_contrast(q: SeasonContrastQuery):
    """Filtered season contrast (supports the same filters used in /query)."""
    filtered, _, _, _ = filter_audit_data(
        events=q.events,
        stars=q.stars,
        catch_ops=q.catch_ops,
        min_samples=q.min_samples
    )
    return get_season_contrast_stats(split_date=q.split_date, filtered_db=filtered)
