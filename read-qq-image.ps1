param([long]$Handle,[string]$ExpectedHeader,[string]$RuntimeId='',[ValidateSet('prepare','check','latest')][string]$Action='prepare',[string]$OutputPath)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$w=[System.Windows.Automation.AutomationElement]::FromHandle([intptr]$Handle)
$all=$w.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
$heads=@($all|Where-Object {$_.Current.ClassName -match '(^|\s)chat-header__contact-name(\s|$)'})
function Canon($v){return ($v -replace '\s','').Normalize([System.Text.NormalizationForm]::FormKC)}
if($heads.Count -ne 1 -or (Canon $heads[0].Current.Name) -ne (Canon $ExpectedHeader)){throw 'Chat changed; no image captured'}
if($Action -eq 'latest'){
 $scrolls=@($all|Where-Object {$_.Current.ClassName -match 'q-scroll-view' -and $_.Current.ClassName -match 'ml-container'})
 if($scrolls.Count -ne 1){throw 'Chat scroll container ambiguous'}
 $scrolls[0].GetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern).SetScrollPercent(-1,100)
 exit 0
}
$pics=@($all|Where-Object {$_.Current.ClassName -match '(^|\s)pic-element(\s|$)' -and ($_.GetRuntimeId() -join ',') -eq $RuntimeId})
if($pics.Count -ne 1){throw 'Original image element no longer present'}
$pic=$pics[0]
if($Action -eq 'prepare'){$pic.GetCurrentPattern([System.Windows.Automation.ScrollItemPattern]::Pattern).ScrollIntoView();Start-Sleep -Milliseconds 400}
$parent=$pic;$viewport=$null
for($i=0;$i -lt 10 -and $parent;$i++){
 if($parent.Current.ClassName -match 'q-scroll-view' -and $parent.Current.ClassName -match 'ml-container'){$viewport=$parent.Current.BoundingRectangle;break}
 $parent=[System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($parent)
}
if(-not $viewport){throw 'No verified chat image viewport'}
$b=$pic.Current.BoundingRectangle;$wr=$w.Current.BoundingRectangle
if($pic.Current.IsOffscreen -or $b.Width -lt 24 -or $b.Height -lt 24 -or $b.Left -lt $viewport.Left -or $b.Top -lt $viewport.Top -or $b.Right -gt $viewport.Right -or $b.Bottom -gt $viewport.Bottom){throw 'Image is clipped or not visible; refusing partial capture'}
if($b.Left -lt $wr.Left -or $b.Top -lt $wr.Top -or $b.Right -gt $wr.Right -or $b.Bottom -gt $wr.Bottom){throw 'Image outside QQ window'}
$result=@{header=$heads[0].Current.Name;runtime_id=$RuntimeId;rect=@($b.X,$b.Y,$b.Width,$b.Height);viewport=@($viewport.X,$viewport.Y,$viewport.Width,$viewport.Height);window=@($wr.X,$wr.Y,$wr.Width,$wr.Height)}
[IO.File]::WriteAllText($OutputPath,(ConvertTo-Json $result -Depth 4),(New-Object Text.UTF8Encoding $false))
