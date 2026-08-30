$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Finite official-source acquisition for Frontier Unit 119. This is not a
# validator, test harness, reusable CLI product, trading program, promotion
# checker, or broker/account query.

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
$family = Join-Path $repo 'lab\research\ads-business-conditions-above-normal-portfolio-state-v1'
$evidence = Join-Path $family 'evidence'
$source = Join-Path $evidence 'source'
$rawRoot = Join-Path $repo 'lab\artifacts\raw\ads-business-conditions-above-normal-portfolio-state-v1'

$productUrl = 'https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/ads'
$vintageUrl = 'https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/ads/ADS_All_Vintages-zip.zip?hash=4E6B77E5055CA510D1E653F4DD7395C2&la=en&sc_lang=en'
$technicalUrl = 'https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/ads/ads-technical-documentation.pdf'

$rawPath = Join-Path $rawRoot 'ADS_All_Vintages_2026-08-27.zip'
$productPath = Join-Path $source 'PHILADELPHIA_FED_ADS_PRODUCT_2026-08-30.html'
$technicalPath = Join-Path $source 'PHILADELPHIA_FED_ADS_TECHNICAL_DOCUMENTATION_2025-10-24.pdf'
$schedulePath = Join-Path $evidence 'ADS_REALTIME_RELEASE_STATE_SCHEDULE_V1.csv'
$snapshotPath = Join-Path $evidence 'ADS_OUTCOME_FREE_DENSITY_SNAPSHOT_V1.json'
$receiptPath = Join-Path $evidence 'ADS_SOURCE_ACQUISITION_RECEIPT_V1.json'

foreach ($path in @($schedulePath, $snapshotPath, $receiptPath)) {
    if (Test-Path -LiteralPath $path) {
        throw "Frozen output already exists: $path"
    }
}

New-Item -ItemType Directory -Force -Path $rawRoot, $source | Out-Null

function Get-Sha256([string]$Path) {
    return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Write-Utf8Lf([string]$Path, [string]$Text) {
    $normalized = $Text -replace "`r`n", "`n"
    if (-not $normalized.EndsWith("`n")) {
        $normalized += "`n"
    }
    [IO.File]::WriteAllText($Path, $normalized, [Text.UTF8Encoding]::new($false))
}

if (-not (Test-Path -LiteralPath $rawPath)) {
    Invoke-WebRequest -Uri $vintageUrl -OutFile $rawPath -Headers @{
        'User-Agent' = 'Project-Zeta-Terminus-Next research acquisition'
    }
}
if (-not (Test-Path -LiteralPath $productPath)) {
    Invoke-WebRequest -Uri $productUrl -OutFile $productPath -Headers @{
        'User-Agent' = 'Project-Zeta-Terminus-Next research acquisition'
    }
}
if (-not (Test-Path -LiteralPath $technicalPath)) {
    Invoke-WebRequest -Uri $technicalUrl -OutFile $technicalPath -Headers @{
        'User-Agent' = 'Project-Zeta-Terminus-Next research acquisition'
    }
}

$expectedArchiveBytes = 164364257
$expectedArchiveSha256 = 'AB265551198B4DD7CA44BC41230DADADEFD4E0B128558AD8960A44F2AE97C5D3'
if ((Get-Item -LiteralPath $rawPath).Length -ne $expectedArchiveBytes) {
    throw "Unexpected official ADS archive size: $((Get-Item -LiteralPath $rawPath).Length)"
}
if ((Get-Sha256 $rawPath) -ne $expectedArchiveSha256) {
    throw "Unexpected official ADS archive digest: $(Get-Sha256 $rawPath)"
}
$productText = [IO.File]::ReadAllText($productPath)
if ($productText -notmatch 'average value of the ADS index is zero' -or
    $productText -notmatch 'updated in real time') {
    throw 'The captured official product page does not contain the frozen ADS semantics.'
}
$technicalHeader = [byte[]]::new(5)
$technicalStream = [IO.File]::OpenRead($technicalPath)
try {
    if ($technicalStream.Read($technicalHeader, 0, $technicalHeader.Length) -ne $technicalHeader.Length -or
        [Text.Encoding]::ASCII.GetString($technicalHeader) -ne '%PDF-') {
        throw 'The captured technical documentation is not a PDF.'
    }
} finally {
    $technicalStream.Dispose()
}

$parserSource = @'
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Xml;

public sealed class AdsVintagePoint
{
    public DateTime ReleaseDate { get; set; }
    public DateTime LastObservationDate { get; set; }
    public double Value { get; set; }
    public int ValueCount { get; set; }
    public int ColumnNumber { get; set; }
}

public static class AdsVintageWorkbookReader
{
    private static int ColumnNumber(string cellReference)
    {
        int value = 0;
        foreach (char item in cellReference)
        {
            if (item < 'A' || item > 'Z') break;
            value = value * 26 + item - 'A' + 1;
        }
        return value;
    }

    private static List<string> ReadSharedStrings(ZipArchive workbook)
    {
        var output = new List<string>();
        using (var stream = workbook.GetEntry("xl/sharedStrings.xml").Open())
        using (var reader = XmlReader.Create(stream, new XmlReaderSettings
        {
            IgnoreWhitespace = true,
            IgnoreComments = true,
            DtdProcessing = DtdProcessing.Prohibit
        }))
        {
            while (reader.Read())
            {
                if (reader.NodeType == XmlNodeType.Element && reader.LocalName == "t")
                    output.Add(reader.ReadElementContentAsString());
            }
        }
        return output;
    }

    public static AdsVintagePoint[] Parse(string archivePath)
    {
        using (var outer = ZipFile.OpenRead(archivePath))
        using (var workbookStream = new MemoryStream())
        {
            if (outer.Entries.Count != 1 ||
                outer.Entries[0].FullName != "ADS_All_Vintages-zip.xlsx" ||
                outer.Entries[0].Length != 199333144)
                throw new InvalidDataException("Unexpected ADS archive member.");
            using (var stream = outer.Entries[0].Open()) stream.CopyTo(workbookStream);
            workbookStream.Position = 0;
            using (var workbook = new ZipArchive(workbookStream, ZipArchiveMode.Read, false))
            {
                var shared = ReadSharedStrings(workbook);
                int headerCount = 1;
                while (headerCount < shared.Count &&
                       shared[headerCount].StartsWith("ADS_INDEX_", StringComparison.Ordinal))
                    headerCount++;
                if (headerCount != 1564)
                    throw new InvalidDataException("Unexpected ADS vintage-column count.");

                var selected = new Dictionary<int, AdsVintagePoint>();
                for (int index = 1; index < headerCount; index++)
                {
                    DateTime releaseDate;
                    if (DateTime.TryParseExact(
                            shared[index].Substring("ADS_INDEX_".Length),
                            "MMddyy",
                            CultureInfo.InvariantCulture,
                            DateTimeStyles.None,
                            out releaseDate) && releaseDate >= new DateTime(2022, 1, 1))
                    {
                        int column = index + 1;
                        selected[column] = new AdsVintagePoint
                        {
                            ReleaseDate = releaseDate,
                            ColumnNumber = column,
                            Value = double.NaN
                        };
                    }
                }

                using (var stream = workbook.GetEntry("xl/worksheets/sheet1.xml").Open())
                using (var reader = XmlReader.Create(stream, new XmlReaderSettings
                {
                    IgnoreWhitespace = true,
                    IgnoreComments = true,
                    DtdProcessing = DtdProcessing.Prohibit
                }))
                {
                    reader.Read();
                    while (!reader.EOF)
                    {
                        if (reader.NodeType == XmlNodeType.Element && reader.LocalName == "row")
                        {
                            int rowNumber = int.Parse(reader.GetAttribute("r"), CultureInfo.InvariantCulture);
                            if (rowNumber == 1)
                            {
                                reader.Skip();
                                continue;
                            }
                            int sharedIndex = headerCount + rowNumber - 2;
                            DateTime observationDate;
                            if (sharedIndex < 0 || sharedIndex >= shared.Count ||
                                !DateTime.TryParseExact(
                                    shared[sharedIndex],
                                    "yyyy:MM:dd",
                                    CultureInfo.InvariantCulture,
                                    DateTimeStyles.None,
                                    out observationDate) || observationDate < new DateTime(2021, 12, 1))
                            {
                                reader.Skip();
                                continue;
                            }

                            using (var row = reader.ReadSubtree())
                            {
                                while (row.Read())
                                {
                                    if (row.NodeType != XmlNodeType.Element || row.LocalName != "c")
                                        continue;
                                    AdsVintagePoint point;
                                    int column = ColumnNumber(row.GetAttribute("r"));
                                    if (!selected.TryGetValue(column, out point))
                                    {
                                        row.Skip();
                                        continue;
                                    }
                                    using (var cell = row.ReadSubtree())
                                    {
                                        while (cell.Read())
                                        {
                                            if (cell.NodeType == XmlNodeType.Element && cell.LocalName == "v")
                                            {
                                                double parsed;
                                                if (double.TryParse(
                                                        cell.ReadElementContentAsString(),
                                                        NumberStyles.Float,
                                                        CultureInfo.InvariantCulture,
                                                        out parsed))
                                                {
                                                    point.Value = parsed;
                                                    point.LastObservationDate = observationDate;
                                                    point.ValueCount++;
                                                }
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                            reader.Read();
                            continue;
                        }
                        reader.Read();
                    }
                }

                var result = new List<AdsVintagePoint>(selected.Values);
                result.Sort((left, right) => left.ReleaseDate.CompareTo(right.ReleaseDate));
                return result.ToArray();
            }
        }
    }
}
'@

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$parserReferences = @(
    [System.Xml.XmlReader].Assembly.Location,
    [System.IO.Compression.ZipArchive].Assembly.Location,
    [System.IO.Compression.ZipFile].Assembly.Location
)
Add-Type -TypeDefinition $parserSource -Language CSharp -ReferencedAssemblies $parserReferences
$points = [AdsVintageWorkbookReader]::Parse($rawPath)
if ($points.Count -ne 385) { throw "Unexpected retained ADS vintages: $($points.Count)" }
if (@($points | Where-Object {
        $_.ValueCount -le 0 -or [double]::IsNaN($_.Value) -or [double]::IsInfinity($_.Value)
    }).Count -ne 0) {
    throw 'One or more ADS vintages lack a finite last observation.'
}
if (@($points | Where-Object { $_.LastObservationDate.Date -ge $_.ReleaseDate.Date }).Count -ne 0) {
    throw 'One or more ADS vintages have a noncausal last observation date.'
}

$expectedYears = @{ 2022 = 85; 2023 = 86; 2024 = 83; 2025 = 80; 2026 = 51 }
foreach ($year in $expectedYears.Keys) {
    $actual = @($points | Where-Object { $_.ReleaseDate.Year -eq $year }).Count
    if ($actual -ne $expectedYears[$year]) { throw "Unexpected $year vintage count: $actual" }
}

$schedule = foreach ($point in $points) {
    [pscustomobject]@{
        release_date = $point.ReleaseDate.ToString('yyyy-MM-dd')
        observation_date = $point.LastObservationDate.ToString('yyyy-MM-dd')
        initial_value = $point.Value.ToString('R', [Globalization.CultureInfo]::InvariantCulture)
        state = if ($point.Value -gt 0.0) { 'ABOVE_NORMAL' } else { 'AT_OR_BELOW_NORMAL' }
        source_column = $point.ColumnNumber
        value_count_from_2021_12 = $point.ValueCount
    }
}
Write-Utf8Lf $schedulePath (($schedule | ConvertTo-Csv -NoTypeInformation) -join "`n")

$components = @{
    'ZT-M30-US30-RANGE-COMP-61f61deaba' = @('RC16', 'US30_BOOK', 'OPEN')
    'ZT-M30-US30-RANGE-COMP-64efb16616' = @('RC4', 'US30_BOOK', 'OPEN')
    'ZT-H1-US100-CROSS-IN-14b72317b7' = @('Cross', 'US100_BOOK', 'OPEN')
    'ZT-M30-US30-INTRADAY-R-2eb111fc46' = @('Pressure', 'US30_BOOK', 'OPEN')
    'ZT-H1-US30-RETURN-I-c870a788ec' = @('Return', 'US30_BOOK', 'OPEN')
    'ZT-M15-US100-IMPULSE-EXTENSION--311868f4e8' = @('Passive', 'US100_BOOK', 'PASSIVE_FILL')
}
$portfolioFiles = @(
    @('P1_2022H2_2023', 'lab/artifacts/ea-files/passive-refusal-depth-observation-v1/valid-p1-2022h2-2023/observation/events-a.csv'),
    @('P1_2022H2_2023', 'lab/artifacts/ea-files/passive-refusal-depth-observation-v1/valid-p1-2022h2-2023/observation/events-b.csv'),
    @('P2_2024', 'lab/artifacts/ea-files/passive-refusal-depth-observation-v1/valid-p2-2024/observation/events-a.csv'),
    @('P3_2025', 'lab/artifacts/ea-files/passive-refusal-depth-observation-v1/valid-p3-2025/observation/events-a.csv'),
    @('P3_2025', 'lab/artifacts/ea-files/passive-refusal-depth-observation-v1/valid-p3-2025/observation/events-b.csv'),
    @('P4_2026_YTD', 'lab/artifacts/ea-files/passive-refusal-depth-observation-v1/valid-p4-2026-ytd/observation/events-a.csv')
)

$births = [Collections.Generic.List[object]]::new()
foreach ($file in $portfolioFiles) {
    $period = $file[0]
    $path = Join-Path $repo $file[1]
    foreach ($row in (Import-Csv -LiteralPath $path | Select-Object server_time, event, component_id)) {
        if (-not $components.ContainsKey($row.component_id)) { continue }
        $component = $components[$row.component_id]
        if ($row.event -ne $component[2]) { continue }
        $birthDate = [datetime]::ParseExact(
            $row.server_time,
            'yyyy.MM.dd HH:mm:ss',
            [Globalization.CultureInfo]::InvariantCulture
        ).Date
        $low = 0
        $high = $points.Count - 1
        $selectedIndex = -1
        while ($low -le $high) {
            $middle = [int](($low + $high) / 2)
            if ($points[$middle].ReleaseDate.Date -lt $birthDate) {
                $selectedIndex = $middle
                $low = $middle + 1
            } else {
                $high = $middle - 1
            }
        }
        $role = if ($selectedIndex -lt 0) {
            'UNAVAILABLE'
        } elseif ($points[$selectedIndex].Value -gt 0.0) {
            'ABOVE_NORMAL'
        } else {
            'AT_OR_BELOW_NORMAL'
        }
        $births.Add([pscustomobject]@{
            period = $period
            component = $component[0]
            book = $component[1]
            role = $role
            release_date = if ($selectedIndex -ge 0) { $points[$selectedIndex].ReleaseDate.ToString('yyyy-MM-dd') } else { '' }
        })
    }
}

if ($births.Count -ne 2233) { throw "Unexpected birth count: $($births.Count)" }
if (@($births | Where-Object role -eq 'UNAVAILABLE').Count -ne 0) { throw 'Unexpected unavailable birth.' }

function Count-Cells([object[]]$Rows, [string[]]$Fields) {
    $output = [ordered]@{}
    foreach ($group in ($Rows | Group-Object -Property $Fields | Sort-Object Name)) {
        $output[$group.Name] = $group.Count
    }
    return $output
}

$releaseStates = @($schedule | ForEach-Object { $_.state })
$signFlips = 0
for ($index = 1; $index -lt $releaseStates.Count; $index++) {
    if ($releaseStates[$index] -ne $releaseStates[$index - 1]) { $signFlips++ }
}

$periodBookCells = @($births | Group-Object period, book, role)
$componentCells = @($births | Group-Object component, role)
$snapshot = [ordered]@{
    schema = 'zeta-next-ads-outcome-free-density-snapshot-v1'
    created_at_local = '2026-08-30'
    status = 'OUTCOME_FREE_CAUSAL_STATE_DENSITY_PASSED'
    source_release_points = $points.Count
    source_release_state_counts = Count-Cells $schedule @('state')
    source_release_sign_flips = $signFlips
    lifecycles = $births.Count
    mapped = @($births | Where-Object role -ne 'UNAVAILABLE').Count
    unavailable = @($births | Where-Object role -eq 'UNAVAILABLE').Count
    state_counts = Count-Cells $births @('role')
    period_state_counts = Count-Cells $births @('period', 'role')
    book_state_counts = Count-Cells $births @('book', 'role')
    component_state_counts = Count-Cells $births @('component', 'role')
    minimum_period_book_state_cell = ($periodBookCells | Measure-Object Count -Minimum).Minimum
    minimum_component_state_cell = ($componentCells | Measure-Object Count -Minimum).Minimum
    unique_used_release_dates = @($births.release_date | Where-Object { $_ } | Sort-Object -Unique).Count
    causal_rule = 'Use only the latest official ADS vintage date strictly earlier than the lifecycle server date; a same-day new vintage is never used.'
    target_economic_fields_accessed = $false
    lifecycle_final_value_planned_risk_stressed_r_stop_accessed = $false
    broker_or_account_state_queried = $false
    live_surface = 'UNTOUCHED'
}
Write-Utf8Lf $snapshotPath (($snapshot | ConvertTo-Json -Depth 10))

$receipt = [ordered]@{
    schema = 'zeta-next-ads-source-acquisition-receipt-v1'
    created_at_local = '2026-08-30'
    status = 'SOURCE_AND_CAUSAL_SCHEDULE_FROZEN_BEFORE_ECONOMIC_AGGREGATION'
    publisher = 'Federal Reserve Bank of Philadelphia'
    product = 'Aruoba-Diebold-Scotti Business Conditions Index'
    product_url = $productUrl
    all_vintages_url = $vintageUrl
    technical_documentation_url = $technicalUrl
    official_semantics = 'The theoretical average is zero; progressively positive values indicate better-than-average and progressively negative values worse-than-average real business conditions.'
    publication_semantics = 'The index is updated in real time after new or revised component releases, about seven to eight times monthly.'
    causal_use = 'Retain the last finite daily estimate in each real-time vintage column and activate it only on a strictly later lifecycle server date.'
    sources = @(
        [ordered]@{ path = $rawPath.Substring($repo.Length + 1).Replace('\','/'); url = $vintageUrl; tracked = $false; bytes = (Get-Item $rawPath).Length; sha256 = Get-Sha256 $rawPath },
        [ordered]@{ path = $productPath.Substring($repo.Length + 1).Replace('\','/'); url = $productUrl; tracked = $true; bytes = (Get-Item $productPath).Length; sha256 = Get-Sha256 $productPath },
        [ordered]@{ path = $technicalPath.Substring($repo.Length + 1).Replace('\','/'); url = $technicalUrl; tracked = $true; bytes = (Get-Item $technicalPath).Length; sha256 = Get-Sha256 $technicalPath },
        [ordered]@{ path = $schedulePath.Substring($repo.Length + 1).Replace('\','/'); tracked = $true; bytes = (Get-Item $schedulePath).Length; sha256 = Get-Sha256 $schedulePath; rows = $points.Count },
        [ordered]@{ path = $snapshotPath.Substring($repo.Length + 1).Replace('\','/'); tracked = $true; bytes = (Get-Item $snapshotPath).Length; sha256 = Get-Sha256 $snapshotPath }
    )
    archive_inner_entry = 'ADS_All_Vintages-zip.xlsx'
    archive_inner_uncompressed_bytes = 199333144
    workbook_vintage_columns_total = 1563
    retained_vintage_rows = $points.Count
    retained_first_release = $points[0].ReleaseDate.ToString('yyyy-MM-dd')
    retained_last_release = $points[-1].ReleaseDate.ToString('yyyy-MM-dd')
    network_calls = 3
    lifecycle_or_economic_outcomes_accessed = $false
    broker_or_account_state_queried = $false
    live_surface = 'UNTOUCHED'
}
Write-Utf8Lf $receiptPath (($receipt | ConvertTo-Json -Depth 10))
$receipt | ConvertTo-Json -Depth 10
