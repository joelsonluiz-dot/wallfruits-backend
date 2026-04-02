$ErrorActionPreference = "Stop"
$baseApi = "http://127.0.0.1:8000/api"
$baseWeb = "http://127.0.0.1:8000"
$results = [ordered]@{}

function Mark-Ok($name, $detail) {
  $results[$name] = @{ status = "OK"; detail = $detail }
}
function Mark-Fail($name, $detail) {
  $results[$name] = @{ status = "FALHA"; detail = $detail }
}

$pages = @("/register","/","/offers","/messages")
foreach ($p in $pages) {
  try {
    $resp = Invoke-WebRequest -Uri ($baseWeb + $p) -Method GET -TimeoutSec 12
    Mark-Ok ("PAGE $p") ("HTTP " + $resp.StatusCode)
  } catch {
    Mark-Fail ("PAGE $p") $_.Exception.Message
  }
}

$email = "smokeflow_" + (Get-Date -Format "yyyyMMddHHmmssfff") + "@wallfruits.test"
$password = "Smoke@12345"
$registerBody = @{
  name = "Smoke Flow User"
  email = $email
  password = $password
  role = "buyer"
  phone = "11999990000"
  location = "Sao Paulo/SP"
} | ConvertTo-Json -Depth 6

$token = $null
$loginUserId = $null

try {
  $reg = Invoke-RestMethod -Uri ($baseApi + "/auth/register") -Method POST -ContentType "application/json" -Body $registerBody -TimeoutSec 20
  Mark-Ok "REGISTER" ("usuario_id=" + $reg.id + " email=" + $reg.email)
} catch {
  Mark-Fail "REGISTER" $_.Exception.Message
}

try {
  $loginBody = @{ email = $email; password = $password } | ConvertTo-Json
  $login = Invoke-RestMethod -Uri ($baseApi + "/auth/login") -Method POST -ContentType "application/json" -Body $loginBody -TimeoutSec 20
  $token = $login.access_token
  $loginUserId = $login.user.id
  if ($token) {
    $prefixLen = [Math]::Min(16, $token.Length)
    Mark-Ok "LOGIN" ("token_prefix=" + $token.Substring(0, $prefixLen) + "...")
  } else {
    Mark-Fail "LOGIN" "sem token na resposta"
  }
} catch {
  Mark-Fail "LOGIN" $_.Exception.Message
}

$authHeaders = @{}
if ($token) { $authHeaders["Authorization"] = "Bearer $token" }

try {
  $offersHome = Invoke-RestMethod -Uri ($baseApi + "/offers?limit=3") -Method GET -Headers $authHeaders -TimeoutSec 20
  $count = @($offersHome.offers).Count
  Mark-Ok "HOME_OFFERS" ("offers=" + $count + " total=" + $offersHome.total)
} catch {
  Mark-Fail "HOME_OFFERS" $_.Exception.Message
}

try {
  $servicesHome = Invoke-RestMethod -Uri ($baseApi + "/services?skip=0&limit=8") -Method GET -Headers $authHeaders -TimeoutSec 20
  $count = @($servicesHome.services).Count
  Mark-Ok "HOME_SERVICES" ("services=" + $count + " total=" + $servicesHome.total)
} catch {
  Mark-Fail "HOME_SERVICES" $_.Exception.Message
}

try {
  $communityHome = Invoke-RestMethod -Uri ($baseApi + "/community/posts?skip=0&limit=6") -Method GET -Headers $authHeaders -TimeoutSec 20
  $count = @($communityHome.posts).Count
  Mark-Ok "HOME_COMMUNITY" ("posts=" + $count)
} catch {
  Mark-Fail "HOME_COMMUNITY" $_.Exception.Message
}

$selectedOffer = $null
try {
  $offersPage = Invoke-RestMethod -Uri ($baseApi + "/offers?skip=0&limit=12") -Method GET -Headers $authHeaders -TimeoutSec 20
  $list = @($offersPage.offers)
  $selectedOffer = $list | Select-Object -First 1
  Mark-Ok "OFFERS_LIST" ("items=" + $list.Count)
} catch {
  Mark-Fail "OFFERS_LIST" $_.Exception.Message
}

if ($selectedOffer -and $token) {
  $offerId = [string]$selectedOffer.id
  $ownerId = $null
  if ($selectedOffer.owner_data -and $selectedOffer.owner_data.id) { $ownerId = [int]$selectedOffer.owner_data.id }
  $productName = [string]$selectedOffer.product_name

  try {
    $favBody = @{ offer_id = $offerId } | ConvertTo-Json
    $fav = Invoke-RestMethod -Uri ($baseApi + "/favorites") -Method POST -Headers $authHeaders -ContentType "application/json" -Body $favBody -TimeoutSec 20
    Mark-Ok "OFFERS_LIKE" ("offer_id=" + $offerId + " favorite_id=" + $fav.id)

    Invoke-RestMethod -Uri ($baseApi + "/favorites/" + $offerId) -Method DELETE -Headers $authHeaders -TimeoutSec 20 | Out-Null
    Mark-Ok "OFFERS_UNLIKE" ("offer_id=" + $offerId)
  } catch {
    Mark-Fail "OFFERS_LIKE_OR_UNLIKE" $_.Exception.Message
  }

  if ($ownerId -and ($loginUserId -ne $ownerId)) {
    try {
      $content = "Olá! Tenho interesse na oferta '" + $productName + "'."
      $msgBody = @{
        receiver_id = $ownerId
        offer_id = $offerId
        message_type = "offer_inquiry"
        subject = ("Interesse em oferta " + $offerId)
        content = $content
      } | ConvertTo-Json -Depth 5

      $sent = Invoke-RestMethod -Uri ($baseApi + "/messages") -Method POST -Headers $authHeaders -ContentType "application/json" -Body $msgBody -TimeoutSec 20
      Mark-Ok "CHAT_SEND_FROM_OFFER" ("thread_id=" + $sent.thread_id)

      $conversations = Invoke-RestMethod -Uri ($baseApi + "/messages/conversations") -Method GET -Headers $authHeaders -TimeoutSec 20
      $convCount = @($conversations).Count
      Mark-Ok "CHAT_HISTORY_LIST" ("conversations=" + $convCount)
    } catch {
      Mark-Fail "CHAT_SEND_OR_HISTORY" $_.Exception.Message
    }
  } else {
    Mark-Fail "CHAT_SEND_FROM_OFFER" "Oferta sem owner válido para teste de chat"
  }
} else {
  Mark-Fail "OFFERS_ACTIONS" "Sem oferta disponível para validar curtir/chat"
}

Write-Output "=== SMOKE FLOW RESULTS ==="
$results.GetEnumerator() | ForEach-Object {
  Write-Output ("{0} | {1} | {2}" -f $_.Key, $_.Value.status, $_.Value.detail)
}
