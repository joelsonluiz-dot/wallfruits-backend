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
function Get-ErrDetail($err) {
  try {
    if ($err.ErrorDetails -and $err.ErrorDetails.Message) {
      return $err.ErrorDetails.Message
    }

    if ($err.Exception.Response -and $err.Exception.Response.GetResponseStream()) {
      $reader = New-Object IO.StreamReader($err.Exception.Response.GetResponseStream())
      $body = $reader.ReadToEnd()
      if ($body) { return $body }

      try {
        if ($err.Exception.Response.StatusCode) {
          return ("HTTP " + [int]$err.Exception.Response.StatusCode.value__ + " - " + $err.Exception.Message)
        }
      } catch {
        # segue para mensagem padrão
      }

      return $err.Exception.Message
    }

    return $err.Exception.Message
  } catch {
    return $err.Exception.Message
  }
}

function Api-PostJson($url, $obj, $headers) {
  $json = $obj | ConvertTo-Json -Depth 8
  return Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $json -Headers $headers -TimeoutSec 25
}

$pages = @("/register","/","/offers","/messages")
foreach ($p in $pages) {
  try {
    $resp = Invoke-WebRequest -Uri ($baseWeb + $p) -Method GET -UseBasicParsing -TimeoutSec 12
    Mark-Ok ("PAGE $p") ("HTTP " + $resp.StatusCode)
  } catch {
    Mark-Fail ("PAGE $p") (Get-ErrDetail $_)
  }
}

$ts = Get-Date -Format "yyyyMMddHHmmssfff"
$emailA = "smokeadmin_${ts}@example.com"
$emailB = "smokebuyer_${ts}@example.com"
$pwd = "Smoke@12345"

$tokenA = $null
$userAId = $null
$tokenB = $null
$userBId = $null
$offerId = $null
$offerOwnerUserId = $null
$threadId = $null
$publisherToken = $null
$publisherUserId = $null
$publisherSource = $null

try {
  $regA = Api-PostJson ($baseApi + "/auth/register") @{
    name = "Smoke Admin"
    email = $emailA
    password = $pwd
    role = "buyer"
    phone = "11999990001"
    location = "Petrolina/PE"
  } @{}
  Mark-Ok "REGISTER_A" ("id=" + $regA.id + " email=" + $regA.email)
} catch {
  Mark-Fail "REGISTER_A" (Get-ErrDetail $_)
}

try {
  $loginA = Api-PostJson ($baseApi + "/auth/login") @{ email = $emailA; password = $pwd } @{}
  $tokenA = $loginA.access_token
  $userAId = $loginA.user.id
  Mark-Ok "LOGIN_A" ("user_id=" + $userAId)
} catch {
  Mark-Fail "LOGIN_A" (Get-ErrDetail $_)
}

if ($tokenA) {
  $headersA = @{ Authorization = "Bearer $tokenA" }

  # Primeiro tenta promover o usuário recém-criado para admin.
  # Se já existir admin no banco, faz fallback para login de um admin existente.
  try {
    $boot = Invoke-RestMethod -Uri ($baseApi + "/auth/bootstrap-admin") -Method POST -Headers $headersA -TimeoutSec 20
    $publisherToken = $tokenA
    $publisherUserId = $userAId
    $publisherSource = "bootstrap-admin"
    Mark-Ok "BOOTSTRAP_ADMIN" ("role=" + $boot.user.role + " source=" + $publisherSource)
  } catch {
    $bootErr = Get-ErrDetail $_
    $bootStatus = $null
    try {
      if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $bootStatus = [int]$_.Exception.Response.StatusCode.value__
      }
    } catch {
      $bootStatus = $null
    }

    $shouldTryExistingAdmin = $false
    if ($bootStatus -eq 403) {
      $shouldTryExistingAdmin = $true
    } elseif ($bootErr -match "Já existe administrador cadastrado|Ja existe administrador cadastrado|ja existe administrador") {
      $shouldTryExistingAdmin = $true
    }

    if ($shouldTryExistingAdmin) {
      $adminEmail = if ([string]::IsNullOrWhiteSpace($env:SMOKE_ADMIN_EMAIL)) { "admin@wallfruits.com.br" } else { $env:SMOKE_ADMIN_EMAIL }
      $adminPassword = if ([string]::IsNullOrWhiteSpace($env:SMOKE_ADMIN_PASSWORD)) { "Admin@2026Wallfruits" } else { $env:SMOKE_ADMIN_PASSWORD }

      try {
        $adminLogin = Api-PostJson ($baseApi + "/auth/login") @{ email = $adminEmail; password = $adminPassword } @{}
        $publisherToken = $adminLogin.access_token
        $publisherUserId = $adminLogin.user.id
        $publisherSource = "existing-admin-login"
        Mark-Ok "BOOTSTRAP_ADMIN" ("admin já existia; fallback com login admin id=" + $publisherUserId)
      } catch {
        Mark-Fail "BOOTSTRAP_ADMIN" ("admin já existia, mas fallback de login falhou: " + (Get-ErrDetail $_))
      }
    } else {
      Mark-Fail "BOOTSTRAP_ADMIN" ($bootErr)
    }
  }

  if ($publisherToken) {
    $publisherHeaders = @{ Authorization = "Bearer $publisherToken" }

    try {
      $offer = Api-PostJson ($baseApi + "/offers") @{
        product_name = "Banana Prata"
        description = "Oferta criada no smoke"
        category = "Frutas"
        quantity = 120
        price = 5.25
        unit = "kg"
        location = "Petrolina/PE"
        organic = $false
        is_negotiable = $true
        min_order = 1
      } $publisherHeaders
      $offerId = [string]$offer.id

      if ($offer.user_id) {
        $offerOwnerUserId = [int]$offer.user_id
      } elseif ($offer.owner_data -and $offer.owner_data.id) {
        $offerOwnerUserId = [int]$offer.owner_data.id
      } elseif ($publisherUserId) {
        $offerOwnerUserId = [int]$publisherUserId
      }

      Mark-Ok "CREATE_OFFER" ("offer_id=" + $offerId + " owner_id=" + $offerOwnerUserId + " source=" + $publisherSource)
    } catch {
      Mark-Fail "CREATE_OFFER" (Get-ErrDetail $_)
    }
  } else {
    Mark-Fail "CREATE_OFFER" "Sem credencial de publicador (bootstrap/login admin)"
  }
}

try {
  $regB = Api-PostJson ($baseApi + "/auth/register") @{
    name = "Smoke Buyer"
    email = $emailB
    password = $pwd
    role = "buyer"
    phone = "11999990002"
    location = "Sao Paulo/SP"
  } @{}
  Mark-Ok "REGISTER_B" ("id=" + $regB.id + " email=" + $regB.email)
} catch {
  Mark-Fail "REGISTER_B" (Get-ErrDetail $_)
}

try {
  $loginB = Api-PostJson ($baseApi + "/auth/login") @{ email = $emailB; password = $pwd } @{}
  $tokenB = $loginB.access_token
  $userBId = $loginB.user.id
  Mark-Ok "LOGIN_B" ("user_id=" + $userBId)
} catch {
  Mark-Fail "LOGIN_B" (Get-ErrDetail $_)
}

if ($tokenB) {
  $headersB = @{ Authorization = "Bearer $tokenB" }

  try {
    $homeOffers = Invoke-RestMethod -Uri ($baseApi + "/offers?limit=3") -Method GET -Headers $headersB -TimeoutSec 20
    Mark-Ok "HOME_OFFERS" ("count=" + @($homeOffers.offers).Count)
  } catch {
    Mark-Fail "HOME_OFFERS" (Get-ErrDetail $_)
  }

  try {
    $homeServices = Invoke-RestMethod -Uri ($baseApi + "/services?skip=0&limit=8") -Method GET -Headers $headersB -TimeoutSec 20
    Mark-Ok "HOME_SERVICES" ("count=" + @($homeServices.services).Count)
  } catch {
    Mark-Fail "HOME_SERVICES" (Get-ErrDetail $_)
  }

  try {
    $homeCommunity = Invoke-RestMethod -Uri ($baseApi + "/community/posts?skip=0&limit=6") -Method GET -Headers $headersB -TimeoutSec 20
    Mark-Ok "HOME_COMMUNITY" ("count=" + @($homeCommunity.posts).Count)
  } catch {
    Mark-Fail "HOME_COMMUNITY" (Get-ErrDetail $_)
  }

  try {
    $offersList = Invoke-RestMethod -Uri ($baseApi + "/offers?skip=0&limit=12") -Method GET -Headers $headersB -TimeoutSec 20
    Mark-Ok "OFFERS_LIST" ("count=" + @($offersList.offers).Count)
  } catch {
    Mark-Fail "OFFERS_LIST" (Get-ErrDetail $_)
  }

  if ($offerId) {
    $chatReceiverId = if ($offerOwnerUserId) { [int]$offerOwnerUserId } else { [int]$userAId }

    try {
      $fav = Api-PostJson ($baseApi + "/favorites") @{ offer_id = $offerId } $headersB
      Mark-Ok "OFFERS_LIKE" ("favorite_id=" + $fav.id)

      Invoke-RestMethod -Uri ($baseApi + "/favorites/" + $offerId) -Method DELETE -Headers $headersB -TimeoutSec 20 | Out-Null
      Mark-Ok "OFFERS_UNLIKE" ("offer_id=" + $offerId)
    } catch {
      Mark-Fail "OFFERS_LIKE_UNLIKE" (Get-ErrDetail $_)
    }

    try {
      $sent = Api-PostJson ($baseApi + "/messages") @{
        receiver_id = $chatReceiverId
        offer_id = $offerId
        message_type = "offer_inquiry"
        subject = ("Interesse em oferta " + $offerId)
        content = "Ola! Tenho interesse na sua oferta."
      } $headersB
      $threadId = [string]$sent.thread_id
      Mark-Ok "CHAT_SEND" ("thread_id=" + $threadId)
    } catch {
      Mark-Fail "CHAT_SEND" (Get-ErrDetail $_)
    }

    try {
      $convs = Invoke-RestMethod -Uri ($baseApi + "/messages/conversations") -Method GET -Headers $headersB -TimeoutSec 20
      Mark-Ok "CHAT_CONVERSATIONS" ("count=" + @($convs).Count)
    } catch {
      Mark-Fail "CHAT_CONVERSATIONS" (Get-ErrDetail $_)
    }

    if ($threadId) {
      try {
        $thread = Invoke-RestMethod -Uri ($baseApi + "/messages/thread/" + $threadId + "?mark_as_read=true") -Method GET -Headers $headersB -TimeoutSec 20
        Mark-Ok "CHAT_THREAD_HISTORY" ("messages=" + @($thread).Count)
      } catch {
        Mark-Fail "CHAT_THREAD_HISTORY" (Get-ErrDetail $_)
      }
    }
  } else {
    Mark-Fail "OFFERS_ACTIONS" "offer_id não disponível para curtir/chat"
  }
}

Write-Output "=== SMOKE FLOW V2 RESULTS ==="
$results.GetEnumerator() | ForEach-Object {
  Write-Output ("{0} | {1} | {2}" -f $_.Key, $_.Value.status, $_.Value.detail)
}
