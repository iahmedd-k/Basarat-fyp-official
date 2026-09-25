$ErrorActionPreference = 'Continue'
$base = 'http://16.16.26.247:8000/api/v1'
$cases = @(
    @{name='stocks.search.symbol'; path='/stocks/search?q=HBL&limit=3'},
    @{name='stocks.search.company'; path='/stocks/search?q=Habib&limit=3'},
    @{name='stocks.search.empty'; path='/stocks/search?q='},
    @{name='stocks.search.limit_invalid'; path='/stocks/search?q=HBL&limit=101'},
    @{name='stocks.overview.HBL'; path='/stocks/HBL/overview'},
    @{name='stocks.history.HBL.1D'; path='/stocks/HBL/price-history?range=1D'},
    @{name='stocks.history.invalid_range'; path='/stocks/HBL/price-history?range=5Y'},
    @{name='stocks.indicators.HBL'; path='/stocks/HBL/technical-indicators?indicators=RSI,MACD,BB,SMA,ADX&period=14&limit=10'},
    @{name='stocks.indicators.invalid_period'; path='/stocks/HBL/technical-indicators?period=0'},
    @{name='stocks.fundamentals.HBL'; path='/stocks/HBL/fundamentals'},
    @{name='stocks.overview.invalid_symbol'; path='/stocks/!!!/overview'},
    @{name='market.sectors.performance'; path='/market/sectors/performance'},
    @{name='market.indices'; path='/market/indices'},
    @{name='market.indices.kse100'; path='/market/indices/kse-100'},
    @{name='market.indices.kse30'; path='/market/indices/kse-30'},
    @{name='market.indices.kmi30'; path='/market/indices/kmi-30'},
    @{name='market.gainers'; path='/market/gainers?limit=5'},
    @{name='market.losers'; path='/market/losers?limit=5'},
    @{name='market.volume_spikes'; path='/market/volume-spikes?limit=5'},
    @{name='market.sentiment'; path='/market/sentiment-overview'},
    @{name='market.quotes.default'; path='/market/quotes?limit=5'},
    @{name='market.quotes.alias'; path='/market/all-stocks?limit=5'},
    @{name='market.quotes.full_universe'; path='/market/quotes?limit=1000'},
    @{name='market.quotes.pagination'; path='/market/quotes?limit=5&offset=2'},
    @{name='market.quotes.symbol_filter'; path='/market/quotes?symbols=HBL,OGDC'},
    @{name='market.quotes.sector_filter'; path='/market/quotes?sector=Bank&limit=5'},
    @{name='market.quotes.search_filter'; path='/market/quotes?search=HBL&limit=5'},
    @{name='market.quotes.sort_asc'; path='/market/quotes?limit=5&sort_by=current&order=asc'},
    @{name='market.quotes.sort_invalid'; path='/market/quotes?limit=5&sort_by=bogus&order=sideways'},
    @{name='market.quotes.invalid_limit'; path='/market/quotes?limit=0'}
)
$out = @()
foreach ($c in $cases) {
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -Uri ($base + $c.path) -TimeoutSec 30 -SkipHttpErrorCheck
        $status = [int]$response.StatusCode
        $content = $response.Content
        $watch.Stop()
        $body = $null; $jsonValid = $false; $topKeys = @(); $itemCount = $null; $sample = $null
        try {
            $body = $content | ConvertFrom-Json -ErrorAction Stop
            $jsonValid = $true
            if ($body -is [System.Management.Automation.PSCustomObject]) { $topKeys = @($body.PSObject.Properties.Name) }
            elseif ($body -is [array]) { $topKeys = @('array') }
            if ($body.PSObject.Properties.Name -contains 'stocks') { $itemCount = @($body.stocks).Count }
            elseif ($body.PSObject.Properties.Name -contains 'bars') { $itemCount = @($body.bars).Count }
            elseif ($body.PSObject.Properties.Name -contains 'results') { $itemCount = @($body.results).Count }
            elseif ($body.PSObject.Properties.Name -contains 'constituents') { $itemCount = @($body.constituents).Count }
            $sample = $content.Substring(0, [Math]::Min(350, $content.Length))
        } catch { $sample = $content.Substring(0, [Math]::Min(350, $content.Length)) }
        $out += [PSCustomObject]@{name=$c.name; path=$c.path; status=$status; seconds=[Math]::Round($watch.Elapsed.TotalSeconds,2); json=$jsonValid; keys=$topKeys; item_count=$itemCount; body_preview=$sample}
    } catch {
        $watch.Stop()
        $out += [PSCustomObject]@{name=$c.name; path=$c.path; status=0; seconds=[Math]::Round($watch.Elapsed.TotalSeconds,2); json=$false; keys=@(); body=$_.Exception.Message}
    }
}
$out | ConvertTo-Json -Depth 20
