use time::{
    format_description::well_known::Iso8601, macros::format_description, OffsetDateTime,
    PrimitiveDateTime,
};

#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub enum SnoozeState {
    Inactive,
    Indefinite,
    Active { until_iso: String },
    Expired,
    Malformed,
}

pub fn evaluate_snooze(iso_string: Option<&str>, now_iso: &str) -> SnoozeState {
    let Some(iso_string) = iso_string else {
        return SnoozeState::Inactive;
    };
    if iso_string == "indefinite" {
        return SnoozeState::Indefinite;
    }

    let Ok(now) = parse_iso_as_utc(now_iso) else {
        return SnoozeState::Malformed;
    };
    let Ok(until) = parse_iso_as_utc(iso_string) else {
        return SnoozeState::Malformed;
    };

    if now >= until {
        SnoozeState::Expired
    } else {
        SnoozeState::Active {
            until_iso: format_utc(until),
        }
    }
}

fn parse_iso_as_utc(value: &str) -> Result<OffsetDateTime, ()> {
    match OffsetDateTime::parse(value, &Iso8601::DEFAULT) {
        Ok(datetime) => Ok(datetime.to_offset(time::UtcOffset::UTC)),
        Err(_) => PrimitiveDateTime::parse(value, &Iso8601::DEFAULT)
            .map(|datetime| datetime.assume_utc())
            .map_err(|_| ()),
    }
}

fn format_utc(value: OffsetDateTime) -> String {
    let format = format_description!("[year]-[month]-[day]T[hour]:[minute]:[second]+00:00");
    value
        .to_offset(time::UtcOffset::UTC)
        .format(&format)
        .expect("UTC ISO formatting should be infallible")
}
