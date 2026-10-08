-- HUD (클라)
-- HP바, 돈 표시(카운트업), 구매 버튼, 스테이지 배너, 토스트, 콤보 카운터(표시 전용).
-- 돈은 leaderstats "돈"의 Changed로, 무기는 Attribute로 자동 복제돼 와요.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local GameFolder = ReplicatedStorage:WaitForChild("Game")
local Config = require(GameFolder:WaitForChild("Config"))
local SoundBank = require(GameFolder:WaitForChild("SoundBank"))

local Hud = {}

local connections = {}
local player = Players.LocalPlayer

-- UI 요소 핸들
local hpFill, hpLabel, moneyLabel, buyButton, buyLabel, bannerLabel, toastLabel, comboLabel
local screenGui

-- 돈 카운트업 상태
local displayMoney = 0
local targetMoney = 0

-- 콤보 (표시 전용 — 판정 영향 0)
local combo = 0
local lastComboTime = 0

-- 토스트·배너 쓰레드 핸들 (겹침 방지)
local toastThread = nil
local bannerThread = nil

local function makeLabel(props, parent)
	local l = Instance.new("TextLabel")
	l.BackgroundTransparency = 1
	l.Font = Enum.Font.FredokaOne
	l.TextColor3 = Color3.new(1, 1, 1)
	l.TextStrokeTransparency = 0.4
	l.TextStrokeColor3 = Color3.fromRGB(30, 30, 40)
	for k, v in pairs(props) do
		l[k] = v
	end
	l.Parent = parent
	return l
end

-- ===== UI 조립 =====
local function buildUI(playerGui)
	screenGui = Instance.new("ScreenGui")
	screenGui.Name = "HUD"
	screenGui.ResetOnSpawn = false
	screenGui.DisplayOrder = 10

	-- [상단 중앙 HP바]
	local hpFrame = Instance.new("Frame")
	hpFrame.Name = "HP틀"
	hpFrame.AnchorPoint = Vector2.new(0.5, 0)
	hpFrame.Position = UDim2.new(0.5, 0, 0, 14)
	hpFrame.Size = UDim2.new(0.5, 0, 0, 34)
	hpFrame.BackgroundColor3 = Color3.fromRGB(35, 38, 48)
	hpFrame.BorderSizePixel = 0
	local frameCorner = Instance.new("UICorner")
	frameCorner.CornerRadius = UDim.new(0, 10)
	frameCorner.Parent = hpFrame

	hpFill = Instance.new("Frame")
	hpFill.Name = "채움"
	hpFill.Position = UDim2.fromOffset(3, 3)
	hpFill.Size = UDim2.new(1, -6, 1, -6)
	hpFill.BackgroundColor3 = Color3.fromRGB(90, 210, 90)
	hpFill.BorderSizePixel = 0
	local fillCorner = Instance.new("UICorner")
	fillCorner.CornerRadius = UDim.new(0, 8)
	fillCorner.Parent = hpFill
	hpFill.Parent = hpFrame

	hpLabel = makeLabel({
		Name = "HP글자",
		Size = UDim2.fromScale(1, 1),
		TextScaled = true,
		Text = "스테이지 1",
	}, hpFrame)
	hpFrame.Parent = screenGui

	-- [좌상단 돈] (HP바보다 아래 y=58 — 좁은 화면에서 HP바와 겹치지 않게)
	local moneyFrame = Instance.new("Frame")
	moneyFrame.Name = "돈틀"
	moneyFrame.Position = UDim2.new(0, 14, 0, 58)
	moneyFrame.Size = UDim2.new(0, 190, 0, 40)
	moneyFrame.BackgroundColor3 = Color3.fromRGB(35, 38, 48)
	moneyFrame.BackgroundTransparency = 0.25
	moneyFrame.BorderSizePixel = 0
	local moneyCorner = Instance.new("UICorner")
	moneyCorner.CornerRadius = UDim.new(0, 10)
	moneyCorner.Parent = moneyFrame
	moneyLabel = makeLabel({
		Name = "돈글자",
		Size = UDim2.new(1, -16, 1, 0),
		Position = UDim2.fromOffset(8, 0),
		TextScaled = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Color3.fromRGB(255, 225, 120),
		Text = "0원",
	}, moneyFrame)
	moneyFrame.Parent = screenGui

	-- [하단 중앙 구매 버튼]
	buyButton = Instance.new("TextButton")
	buyButton.Name = "구매버튼"
	buyButton.AnchorPoint = Vector2.new(0.5, 1)
	buyButton.Position = UDim2.new(0.5, 0, 1, -18)
	buyButton.Size = UDim2.new(0, 340, 0, 56)
	buyButton.BackgroundColor3 = Color3.fromRGB(255, 205, 60)
	buyButton.BorderSizePixel = 0
	buyButton.Text = ""
	buyButton.AutoButtonColor = true
	local buyCorner = Instance.new("UICorner")
	buyCorner.CornerRadius = UDim.new(0, 14)
	buyCorner.Parent = buyButton
	buyLabel = makeLabel({
		Name = "구매글자",
		Size = UDim2.new(1, -16, 1, -8),
		Position = UDim2.fromOffset(8, 4),
		TextScaled = true,
		TextColor3 = Color3.fromRGB(50, 40, 10),
		TextStrokeTransparency = 1,
		Text = "...",
	}, buyButton)
	buyButton.Parent = screenGui

	-- [중앙 배너] (스테이지!/와르르!!)
	bannerLabel = makeLabel({
		Name = "배너",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.35),
		Size = UDim2.new(0.8, 0, 0, 90),
		TextScaled = true,
		Text = "",
		Visible = false,
		TextColor3 = Color3.fromRGB(255, 240, 150),
	}, screenGui)

	-- [토스트] (구매 성공/실패 안내)
	toastLabel = makeLabel({
		Name = "토스트",
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -86),
		Size = UDim2.new(0.7, 0, 0, 34),
		TextScaled = true,
		Text = "",
		Visible = false,
	}, screenGui)

	-- [콤보 카운터] (우측, 표시 전용)
	comboLabel = makeLabel({
		Name = "콤보",
		AnchorPoint = Vector2.new(1, 0.5),
		Position = UDim2.new(1, -24, 0.4, 0),
		Size = UDim2.new(0, 170, 0, 54),
		TextScaled = true,
		Text = "",
		Visible = false,
		TextColor3 = Color3.fromRGB(255, 170, 60),
	}, screenGui)

	screenGui.Parent = playerGui
end

-- ===== 공개 함수들 =====

-- HP바 즉시 갱신 (+색 구간: >50% 초록 / 20~50% 주황 / ≤20% 빨강)
function Hud.UpdateHP(stage, hp, maxHp)
	if not hpFill then
		return
	end
	local ratio = (maxHp > 0) and math.clamp(hp / maxHp, 0, 1) or 0
	hpFill.Size = UDim2.new(ratio, -6, 1, -6)
	if ratio > 0.5 then
		hpFill.BackgroundColor3 = Color3.fromRGB(90, 210, 90)
	elseif ratio > 0.2 then
		hpFill.BackgroundColor3 = Color3.fromRGB(245, 160, 50)
	else
		hpFill.BackgroundColor3 = Color3.fromRGB(235, 70, 60)
	end
	hpLabel.Text = string.format("스테이지 %d · %s / %s",
		stage, Config.comma(math.max(0, hp)), Config.comma(maxHp))
end

-- HP바 0→100% 차오르기 (새 건물 등장 후 0.4초)
function Hud.FillHP(stage, maxHp)
	if not hpFill then
		return
	end
	hpFill.Size = UDim2.new(0, -6, 1, -6)
	hpFill.BackgroundColor3 = Color3.fromRGB(90, 210, 90)
	TweenService:Create(hpFill,
		TweenInfo.new(0.4, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),
		{Size = UDim2.new(1, -6, 1, -6)}):Play()
	hpLabel.Text = string.format("스테이지 %d · %s / %s",
		stage, Config.comma(maxHp), Config.comma(maxHp))
end

-- "+N원" 초록 미니팝
local function moneyPop(delta)
	if not screenGui then
		return
	end
	local pop = makeLabel({
		Name = "돈팝",
		Position = UDim2.new(0, 210, 0, 62),
		Size = UDim2.new(0, 140, 0, 30),
		TextScaled = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Color3.fromRGB(120, 255, 130),
		Text = "+" .. Config.comma(delta) .. "원",
	}, screenGui)
	local tween = TweenService:Create(pop,
		TweenInfo.new(0.55, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),
		{Position = UDim2.new(0, 210, 0, 36), TextTransparency = 1, TextStrokeTransparency = 1})
	tween:Play()
	tween.Completed:Connect(function()
		pop:Destroy()
	end)
end

-- 구매 버튼 글자 갱신 (무기/강화 + 가격, 부족하면 회색)
function Hud.UpdateBuyButton()
	if not buyButton then
		return
	end
	local tier = player:GetAttribute("WeaponId") or 1
	local enh = player:GetAttribute("EnhLevel") or 0
	local price, label
	if tier < #Config.weapons then
		local nextWeapon = Config.weapons[tier + 1]
		price = nextWeapon.price
		label = string.format("다음 무기: %s (%s원)", nextWeapon.name, Config.formatMoney(price))
	else
		price = Config.enhancePrice(enh + 1)
		label = string.format("황금 로켓펀치 +%d 강화 (%s원)", enh + 1, Config.formatMoney(price))
	end
	local enough = targetMoney >= price
	buyLabel.Text = enough and label
		or (label .. " — " .. Config.formatMoney(price - targetMoney) .. "원 부족")
	buyButton.BackgroundColor3 = enough and Color3.fromRGB(255, 205, 60) or Color3.fromRGB(130, 130, 135)
	buyLabel.TextColor3 = enough and Color3.fromRGB(50, 40, 10) or Color3.fromRGB(70, 70, 75)
end

-- 토스트 (성공=노랑 / 실패=빨강)
function Hud.Toast(msg, isFail)
	if not toastLabel then
		return
	end
	toastLabel.Text = msg
	toastLabel.TextColor3 = isFail and Color3.fromRGB(255, 110, 100) or Color3.fromRGB(255, 240, 150)
	toastLabel.TextTransparency = 0
	toastLabel.TextStrokeTransparency = 0.4
	toastLabel.Visible = true
	if toastThread then
		task.cancel(toastThread)
	end
	toastThread = task.delay(1.6, function()
		local tween = TweenService:Create(toastLabel,
			TweenInfo.new(0.4),
			{TextTransparency = 1, TextStrokeTransparency = 1})
		tween:Play()
		tween.Completed:Connect(function()
			toastLabel.Visible = false
		end)
	end)
end

-- 중앙 배너 ("스테이지 n!" / "와르르!!") — 크게 나타났다가 줄어드는 팝
function Hud.Banner(text, rotation, duration)
	if not bannerLabel then
		return
	end
	bannerLabel.Text = text
	bannerLabel.Rotation = rotation or 0
	bannerLabel.TextTransparency = 0
	bannerLabel.TextStrokeTransparency = 0.4
	bannerLabel.Visible = true
	bannerLabel.Size = UDim2.new(1.2, 0, 0, 135)  -- 1.5배 크기에서 시작
	TweenService:Create(bannerLabel,
		TweenInfo.new(0.3, Enum.EasingStyle.Back, Enum.EasingDirection.Out),
		{Size = UDim2.new(0.8, 0, 0, 90)}):Play()
	if bannerThread then
		task.cancel(bannerThread)
	end
	bannerThread = task.delay(duration or 1.2, function()
		local fade = TweenService:Create(bannerLabel,
			TweenInfo.new(0.35),
			{TextTransparency = 1, TextStrokeTransparency = 1})
		fade:Play()
		fade.Completed:Connect(function()
			bannerLabel.Visible = false
		end)
	end)
end

-- 콤보 +1 (내 타격 때만, 표시 전용)
function Hud.AddCombo()
	combo += 1
	lastComboTime = os.clock()
	if combo >= 2 and comboLabel then
		comboLabel.Text = "x " .. combo
		comboLabel.Visible = true
		comboLabel.TextTransparency = 0
		comboLabel.TextStrokeTransparency = 0.4
		comboLabel.Rotation = math.random(-6, 6)
	end
	return combo
end

-- 구매 버튼 흔들림 (실패 연출)
function Hud.ShakeButton()
	if not buyButton then
		return
	end
	task.spawn(function()
		local origin = buyButton.Position
		for _ = 1, 5 do
			buyButton.Position = origin + UDim2.fromOffset(math.random(-6, 6), 0)
			task.wait(0.05)
		end
		buyButton.Position = origin
	end)
end

function Hud.Init(remotes, fx)
	local playerGui = player:WaitForChild("PlayerGui")
	buildUI(playerGui)

	-- 돈: leaderstats 구독 (카운트업 + 미니팝)
	task.spawn(function()
		local stats = player:WaitForChild("leaderstats", 30)
		if not stats then
			return
		end
		local moneyValue = stats:WaitForChild("돈", 30)
		if not moneyValue then
			return
		end
		displayMoney = moneyValue.Value
		targetMoney = moneyValue.Value
		moneyLabel.Text = Config.formatMoney(displayMoney) .. "원"
		Hud.UpdateBuyButton()
		table.insert(connections, moneyValue.Changed:Connect(function(newValue)
			local delta = newValue - targetMoney
			targetMoney = newValue
			if delta > 0 then
				moneyPop(delta)
			end
			Hud.UpdateBuyButton()
		end))
	end)

	-- 매 프레임: 돈 카운트업(약 0.4초에 따라붙음) + 콤보 타임아웃
	table.insert(connections, RunService.RenderStepped:Connect(function(dt)
		if math.abs(targetMoney - displayMoney) > 0.5 then
			displayMoney += (targetMoney - displayMoney) * math.min(1, dt * 8)
			if math.abs(targetMoney - displayMoney) < 1 then
				displayMoney = targetMoney
			end
			moneyLabel.Text = Config.formatMoney(displayMoney) .. "원"
		end
		-- 콤보: 1.2초 무타격 시 페이드
		if combo > 0 and os.clock() - lastComboTime > 1.2 then
			combo = 0
			if comboLabel.Visible then
				local fade = TweenService:Create(comboLabel,
					TweenInfo.new(0.3),
					{TextTransparency = 1, TextStrokeTransparency = 1})
				fade:Play()
				fade.Completed:Connect(function()
					comboLabel.Visible = false
				end)
			end
		end
	end))

	-- 무기·강화 바뀌면 버튼 갱신
	table.insert(connections, player:GetAttributeChangedSignal("WeaponId"):Connect(Hud.UpdateBuyButton))
	table.insert(connections, player:GetAttributeChangedSignal("EnhLevel"):Connect(Hud.UpdateBuyButton))

	-- 구매 버튼 → 서버 Invoke (pcall 필수)
	table.insert(connections, buyButton.Activated:Connect(function()
		local ok, success, msg = pcall(function()
			return remotes.Buy:InvokeServer()
		end)
		if not ok then
			Hud.Toast("서버와 연결이 잠깐 끊겼어요", true)
			return
		end
		if success then
			Hud.Toast(msg, false)
			if fx and fx.WeaponPopFx then
				fx.WeaponPopFx()
			end
			SoundBank.play("ping", {pitch = 1.1, volume = 0.6})
		else
			Hud.Toast(msg, true)
			Hud.ShakeButton()
			SoundBank.play("ouch", {volume = 0.5})
		end
		Hud.UpdateBuyButton()
	end))

	Hud.UpdateBuyButton()
end

return Hud
