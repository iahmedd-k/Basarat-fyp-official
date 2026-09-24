$base = 'http://16.16.26.247:8000/api/v1'
$quotes = Invoke-RestMethod -Uri "$base/market/quotes?limit=1000"
$items = @($quotes.stocks)
$zeroCurrent = @($items | Where-Object { $_.current -eq 0 }).Count
$zeroOpen = @($items | Where-Object { $_.open -eq 0 }).Count
$zeroHigh = @($items | Where-Object { $_.high -eq 0 }).Count
$zeroLow = @($items | Where-Object { $_.low -eq 0 }).Count
$zeroVolume = @($items | Where-Object { $_.volume -eq 0 }).Count
$capZero = @($items | Where-Object { $_.market_cap_m -eq 0 }).Count
$badChange = @($items | Where-Object { [Math]::Abs(($_.current - $_.ldcp) - $_.change) -gt 0.02 }).Count
$bars = Invoke-RestMethod -Uri "$base/stocks/HBL/price-history?range=1D"
$fund = Invoke-RestMethod -Uri "$base/stocks/HBL/fundamentals"
$overview = Invoke-RestMethod -Uri "$base/stocks/HBL/overview"
[PSCustomObject]@{
    quote_total=$quotes.total; returned=$items.Count; quote_as_of=$quotes.as_of; quote_is_stale=$quotes.is_stale
    zero_current=$zeroCurrent; zero_open=$zeroOpen; zero_high=$zeroHigh; zero_low=$zeroLow; zero_volume=$zeroVolume; zero_market_cap=$capZero; arithmetic_change_mismatch=$badChange
    quote_samples_zero_current=@($items | Where-Object { $_.current -eq 0 } | Select-Object -First 5 symbol,ldcp,current,volume)
    quote_samples_extreme_decliners=@($items | Sort-Object change_pct | Select-Object -First 5 symbol,ldcp,current,change,change_pct,volume)
    hbl_history_range=$bars.range; hbl_history_bars=@($bars.bars).Count; hbl_history_as_of=$bars.as_of_date; hbl_history_age_days=$bars.data_age_days; hbl_history_stale=$bars.is_stale
    hbl_overview_day_range=$overview.day_range; hbl_overview_stale=$overview.quote_is_stale
    hbl_fundamentals_status=$fund.data_status; fundamentals_null_fields=@($fund.PSObject.Properties | Where-Object { $null -eq $_.Value } | Select-Object -ExpandProperty Name); hbl_fundamentals_message=$fund.data_message
} | ConvertTo-Json -Depth 8
