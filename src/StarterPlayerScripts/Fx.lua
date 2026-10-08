-- 연출 (클라)
-- 무기 리그·스윙 애니, 타격 임팩트(플래시·스파크·파편·소리), 데미지 숫자 팝업,
-- 파손 단계 연출, 붕괴 스펙터클, 새 건물 층별 등장까지 눈이 즐거운 전부!

local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local GameFolder = ReplicatedStorage:WaitForChild("Game")
local Config = require(GameFolder:WaitForChild("Config"))
local SoundBank = require(GameFolder:WaitForChild("SoundBank"))

local Fx = {}

local player = Players.LocalPlayer
local cameraShake = nil  -- Camera.Shake 를 Init에서 주입받음

local connections = {}

-- UserId별 무기 리그 캐시 (퇴장 시 파괴)
local rigs = {}
-- 데미지 숫자 풀 (20개 재사용)
local numberPool = {}
-- 흰 가장자리 플래시 Frame 4개 + 풀화면 플래시
local edgeFrames = {}
local fullFlash = nil
-- 무기 리그가 둥실거리는 기준 높이
local rigBaseY = 6

-- ========== 무기 리그 ==========

-- 무기 머리 파트 모양 (tier별로 간단히 다르게)
local function makeWeaponHead(tier)
	local info = Config.weapons[tier]
	local head = Instance.new("Part")
	head.Name = "무기머리"
	head.Anchored = true
	head.CanCollide = false
	head.CanTouch = false
	head.CanQuery = false
	head.Material = Enum.Material.SmoothPlastic
	head.Color = info.color

	if tier == 1 then
		head.Size = Vector3.new(2.2, 2.2, 2.6)  -- 주먹
	elseif tier == 2 or tier == 3 then
		head.Size = Vector3.new(3.2, 2.4, 2.4)  -- 망치 머리
		head.Material = (tier == 3) and Enum.Material.Metal or Enum.Material.Wood
	elseif tier == 4 then
		head.Size = Vector3.new(3.6, 3.0, 0.9)  -- 도끼 날
		head.Material = Enum.Material.Metal
	elseif tier == 5 then
		head.Size = Vector3.new(4.6, 1.6, 0.8)  -- 전기톱 바
		head.Material = Enum.Material.Metal
	elseif tier == 6 then
		head.Size = Vector3.new(1.8, 1.8, 4.2)  -- 드릴
		head.Material = Enum.Material.DiamondPlate
	else
		head.Size = Vector3.new(3.0, 3.0, 3.4)  -- 로켓 주먹 (7·8)
		head.Material = Enum.Material.Metal
	end
	return head
end

-- 리그 생성/교체. 자기 것도 남의 것도 같은 코드 재사용
local function makeRig(userId, tier)
	local old = rigs[userId]
	if old and old.model then
		old.model:Destroy()
	end

	local model = Instance.new("Model")
	model.Name = "무기리그_" .. userId

	local head = makeWeaponHead(tier)

	-- 손잡이 (얇은 막대)
	local handle = Instance.new("Part")
	handle.Name = "손잡이"
	handle.Size = Vector3.new(0.6, 3.4, 0.6)
	handle.Anchored = true
	handle.CanCollide = false
	handle.CanTouch = false
	handle.CanQuery = false
	handle.Color = Color3.fromRGB(120, 90, 60)
	handle.Material = Enum.Material.Wood

	-- 8단계: 상시 금색 스파크 Emitter
	if tier == 8 then
		local sparkle = Instance.new("ParticleEmitter")
		sparkle.Name = "황금스파크"
		sparkle.Rate = 20
		sparkle.Lifetime = NumberRange.new(0.2, 0.5)
		sparkle.Speed = NumberRange.new(2, 6)
		sparkle.Color = ColorSequence.new(Color3.fromRGB(255, 220, 90))
		sparkle.Size = NumberSequence.new(0.35)
		sparkle.LightEmission = 1
		sparkle.Parent = head
	end

	head.Parent = model
	handle.Parent = model
	model.Parent = Workspace

	local rig = {
		model = model,
		head = head,
		handle = handle,
		tier = tier,
		bobPhase = math.random() * 6.28,
		swingOffset = CFrame.new(),  -- 스윙 애니가 덮어쓰는 추가 오프셋
		animToken = 0,               -- 새 스윙이 이전 스윙을 끊는 표식
	}
	rigs[userId] = rig
	return rig
end

-- 리그 기준 위치: 건물 옆 (폭/2+7, 기준높이, 깊이/2+2)
local function rigBase()
	return CFrame.new(
		Config.building.width / 2 + 7,
		rigBaseY,
		Config.building.depth / 2 + 2
	)
end

-- 매 프레임 리그 위치 갱신 (대기 둥실 + 스윙 오프셋)
local function updateRigs(dt)
	for _, rig in pairs(rigs) do
		if rig.model and rig.model.Parent then
			rig.bobPhase += dt * 2.2
			local bobY = math.sin(rig.bobPhase) * 0.6
			local cf = rigBase() * CFrame.new(0, bobY, 0) * rig.swingOffset
			-- 머리는 건물 쪽(-X)을 향하게 90도 돌림
			rig.head.CFrame = cf * CFrame.Angles(0, math.rad(90), 0)
			rig.handle.CFrame = cf * CFrame.new(2.2, -0.6, 0) * CFrame.Angles(0, 0, math.rad(20))
		end
	end
end

-- ========== 스윙 절차 애니 (CFrame 오프셋 보간) ==========

-- 지금 코루틴에서 swingOffset을 target까지 duration초 동안 보간
local function lerpOffset(rig, token, target, duration)
	local start = rig.swingOffset
	local t0 = os.clock()
	while rig.animToken == token do
		local a = math.min(1, (os.clock() - t0) / duration)
		rig.swingOffset = start:Lerp(target, a)
		if a >= 1 then
			return true
		end
		RunService.RenderStepped:Wait()
	end
	return false  -- 새 스윙이 끼어듦
end

-- 단계 목록을 순서대로 재생 (새 스윙이 오면 즉시 중단)
local function playSteps(rig, steps)
	rig.animToken += 1
	local token = rig.animToken
	task.spawn(function()
		for _, step in ipairs(steps) do
			if not lerpOffset(rig, token, step[1], step[2]) then
				return
			end
		end
		if rig.animToken == token then
			rig.swingOffset = CFrame.new()
		end
	end)
	return token
end

-- 잔상 WedgePart 3개 (도끼 베기용)
local function slashTrail(rig)
	for i = 1, 3 do
		local w = Instance.new("WedgePart")
		w.Size = Vector3.new(0.4, 3, 5)
		w.Anchored = true
		w.CanCollide = false
		w.CanTouch = false
		w.CanQuery = false
		w.Material = Enum.Material.Neon
		w.Color = Config.weapons[rig.tier].color
		w.Transparency = 0.4 + i * 0.15
		w.CFrame = rig.head.CFrame * CFrame.new(0, -i * 1.4, 0) * CFrame.Angles(math.rad(i * 15), 0, 0)
		w.Parent = Workspace
		TweenService:Create(w, TweenInfo.new(0.25), {Transparency = 1}):Play()
		Debris:AddItem(w, 0.3)
	end
end

-- tier별 스윙 (선반영 — 클릭 즉시)
local function playSwing(rig)
	local tier = rig.tier
	local info = Config.weapons[tier]
	SoundBank.play(info.swing, {pitch = info.swingPitch, volume = 0.35})

	if tier == 1 then
		-- 펀치형: 당김 50ms → 전진 70ms → 복귀 180ms
		playSteps(rig, {
			{CFrame.new(3, 0, 0), 0.05},
			{CFrame.new(-7, 0, 0), 0.07},
			{CFrame.new(), 0.18},
		})
	elseif tier == 2 or tier == 3 then
		-- 내려찍기형: Z회전 윈드업 → 내려침
		playSteps(rig, {
			{CFrame.new(1, 2, 0) * CFrame.Angles(0, 0, math.rad(55)), 0.09},
			{CFrame.new(-5, -1.5, 0) * CFrame.Angles(0, 0, math.rad(-40)), 0.07},
			{CFrame.new(), 0.18},
		})
	elseif tier == 4 then
		-- 수직 베기 + 잔상
		playSteps(rig, {
			{CFrame.new(0.5, 3, 0) * CFrame.Angles(0, 0, math.rad(70)), 0.1},
			{CFrame.new(-5, -2.5, 0) * CFrame.Angles(0, 0, math.rad(-60)), 0.07},
			{CFrame.new(), 0.2},
		})
		task.delay(0.1, slashTrail, rig)
	elseif tier == 5 or tier == 6 then
		-- 찌르고 0.25초 부르르 (한 코루틴에서 순서대로 — 겹침 없음)
		rig.animToken += 1
		local token = rig.animToken
		task.spawn(function()
			if not lerpOffset(rig, token, CFrame.new(-5.5, 0, 0), 0.08) then
				return
			end
			local t0 = os.clock()
			while rig.animToken == token and os.clock() - t0 < 0.25 do
				rig.swingOffset = CFrame.new(
					-5.5 + (math.random() - 0.5) * 0.8,
					(math.random() - 0.5) * 0.8,
					(math.random() - 0.5) * 0.5
				)
				RunService.RenderStepped:Wait()
			end
			if lerpOffset(rig, token, CFrame.new(), 0.15) and rig.animToken == token then
				rig.swingOffset = CFrame.new()
			end
		end)
	else
		-- 7·8: 주먹 발사(비행 120ms) → 귀환 220ms
		playSteps(rig, {
			{CFrame.new(-14, 0, 0), 0.12},
			{CFrame.new(), 0.22},
		})
	end
end

-- 내 스윙 선반영 (Input이 호출)
function Fx.StartSwing()
	local tier = player:GetAttribute("WeaponId") or 1
	local rig = rigs[player.UserId]
	if not rig or rig.tier ~= tier then
		rig = makeRig(player.UserId, tier)
	end
	playSwing(rig)
end

-- 구매 성공 팝 연출 (Hud가 호출): 축소 → 새 무기 팝 + 스파크
function Fx.WeaponPopFx()
	local tier = player:GetAttribute("WeaponId") or 1
	local old = rigs[player.UserId]
	task.spawn(function()
		-- 기존 무기 축소 0.15초
		if old and old.head and old.head.Parent then
			local shrink = TweenService:Create(old.head, TweenInfo.new(0.15),
				{Size = old.head.Size * 0.05, Transparency = 1})
			shrink:Play()
			shrink.Completed:Wait()
		end
		-- 새 무기 1.4→1.0배 팝 + unsheath + 이펙트색 스파크
		local rig = makeRig(player.UserId, tier)
		SoundBank.play("unsheath", {volume = 0.6})
		local fullSize = rig.head.Size
		rig.head.Size = fullSize * 1.4
		TweenService:Create(rig.head,
			TweenInfo.new(0.25, Enum.EasingStyle.Back, Enum.EasingDirection.Out),
			{Size = fullSize}):Play()
		local spark = Instance.new("ParticleEmitter")
		spark.Rate = 0
		spark.Lifetime = NumberRange.new(0.2, 0.5)
		spark.Speed = NumberRange.new(8, 16)
		spark.Color = ColorSequence.new(Config.weapons[tier].color)
		spark.Size = NumberSequence.new(0.4)
		spark.LightEmission = 1
		spark.Parent = rig.head
		spark:Emit(20)
		Debris:AddItem(spark, 1)
	end)
end

-- ========== 데미지 숫자 (ScreenGui + WorldToViewportPoint, 풀 20개) ==========

local function buildNumberPool(playerGui)
	local gui = Instance.new("ScreenGui")
	gui.Name = "데미지숫자"
	gui.ResetOnSpawn = false
	gui.DisplayOrder = 5
	for i = 1, 20 do
		local l = Instance.new("TextLabel")
		l.Name = "숫자" .. i
		l.BackgroundTransparency = 1
		l.Font = Enum.Font.FredokaOne
		l.TextSize = 30
		l.TextColor3 = Color3.new(1, 1, 1)
		l.TextStrokeTransparency = 0.2
		l.TextStrokeColor3 = Color3.fromRGB(30, 30, 40)
		l.Size = UDim2.fromOffset(220, 60)
		l.AnchorPoint = Vector2.new(0.5, 0.5)
		l.Visible = false
		l.Parent = gui
		table.insert(numberPool, {label = l, busy = false})
	end
	gui.Parent = playerGui
end

local function borrowNumber()
	for _, item in ipairs(numberPool) do
		if not item.busy then
			item.busy = true
			return item
		end
	end
	return nil  -- 전부 쓰는 중이면 생략 (연타 폭주 보호)
end

local function showDamage(damage, isCrit, hitPos)
	local item = borrowNumber()
	if not item then
		return
	end
	local l = item.label
	-- CurrentCamera는 교체될 수 있으니 캐시하지 말고 매번 새로 읽어요
	local cam = Workspace.CurrentCamera
	if not cam then
		item.busy = false
		return
	end
	local screenPoint, visible = cam:WorldToViewportPoint(hitPos)
	if not visible then
		item.busy = false
		return
	end
	local x = screenPoint.X + math.random(-30, 30)
	local y = screenPoint.Y + math.random(-15, 15)
	l.Text = Config.comma(damage) .. (isCrit and "\n크리티컬!" or "")
	l.TextSize = isCrit and 54 or 30  -- 크리 = 1.8배 크기
	l.TextColor3 = isCrit and Color3.fromRGB(255, 200, 60) or Color3.new(1, 1, 1)
	l.TextTransparency = 0
	l.TextStrokeTransparency = 0.2
	l.Position = UDim2.fromOffset(x, y)
	l.Visible = true
	-- 0.6초 동안 위로 40px + 페이드
	local tween = TweenService:Create(l,
		TweenInfo.new(0.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out),
		{Position = UDim2.fromOffset(x, y - 40), TextTransparency = 1, TextStrokeTransparency = 1})
	tween:Play()
	tween.Completed:Connect(function()
		l.Visible = false
		item.busy = false
	end)
end

-- ========== 화면 플래시 ==========

local function buildFlash(playerGui)
	local gui = Instance.new("ScreenGui")
	gui.Name = "플래시"
	gui.ResetOnSpawn = false
	gui.IgnoreGuiInset = true
	gui.DisplayOrder = 20

	-- 풀화면 플래시 (붕괴용)
	fullFlash = Instance.new("Frame")
	fullFlash.Size = UDim2.fromScale(1, 1)
	fullFlash.BackgroundColor3 = Color3.new(1, 1, 1)
	fullFlash.BackgroundTransparency = 1
	fullFlash.BorderSizePixel = 0
	fullFlash.ZIndex = 5
	fullFlash.Parent = gui

	-- 가장자리 4변 (크리용)
	local sides = {
		{UDim2.fromScale(1, 0.04), UDim2.fromScale(0, 0)},      -- 위
		{UDim2.fromScale(1, 0.04), UDim2.fromScale(0, 0.96)},   -- 아래
		{UDim2.fromScale(0.025, 1), UDim2.fromScale(0, 0)},     -- 왼쪽
		{UDim2.fromScale(0.025, 1), UDim2.fromScale(0.975, 0)}, -- 오른쪽
	}
	for _, info in ipairs(sides) do
		local f = Instance.new("Frame")
		f.Size = info[1]
		f.Position = info[2]
		f.BackgroundColor3 = Color3.new(1, 1, 1)
		f.BackgroundTransparency = 1
		f.BorderSizePixel = 0
		f.Parent = gui
		table.insert(edgeFrames, f)
	end
	gui.Parent = playerGui
end

local function critEdgeFlash()
	for _, f in ipairs(edgeFrames) do
		f.BackgroundTransparency = 0.55
		TweenService:Create(f, TweenInfo.new(0.3), {BackgroundTransparency = 1}):Play()
	end
end

local function fullScreenFlash()
	if fullFlash then
		fullFlash.BackgroundTransparency = 0.25
		TweenService:Create(fullFlash, TweenInfo.new(0.3), {BackgroundTransparency = 1}):Play()
	end
end

-- ========== 임팩트 5종 세트 ==========

local function impact(tier, isCrit, hitPos)
	local info = Config.weapons[tier] or Config.weapons[1]

	-- ① 히트 플래시: 맞은 블록 자리에 살짝 큰 네온 흰 파트 (0.12초)
	local flash = Instance.new("Part")
	flash.Size = Config.building.blockSize + Vector3.new(0.3, 0.3, 0.3)
	flash.CFrame = CFrame.new(
		hitPos.X >= 0 and 6 or -6,
		math.floor(hitPos.Y / Config.building.floorHeight) * Config.building.floorHeight + 3,
		3.5
	)
	flash.Anchored = true
	flash.CanCollide = false
	flash.CanTouch = false
	flash.CanQuery = false
	flash.Material = Enum.Material.Neon
	flash.Color = Color3.new(1, 1, 1)
	flash.Transparency = 0.15
	flash.Parent = Workspace
	TweenService:Create(flash, TweenInfo.new(0.12), {Transparency = 1}):Play()
	Debris:AddItem(flash, 0.15)

	-- ②③ 스파크 + 회색 파편 (일회성 Emit)
	local point = Instance.new("Part")
	point.Size = Vector3.new(0.2, 0.2, 0.2)
	point.Transparency = 1
	point.Anchored = true
	point.CanCollide = false
	point.CanTouch = false
	point.CanQuery = false
	point.CFrame = CFrame.new(hitPos)

	local spark = Instance.new("ParticleEmitter")
	spark.Rate = 0
	spark.Lifetime = NumberRange.new(0.15, 0.35)
	spark.Speed = NumberRange.new(14, 26)
	spark.Color = ColorSequence.new(info.color)
	spark.Size = NumberSequence.new(0.35)
	spark.LightEmission = 1
	spark.SpreadAngle = Vector2.new(180, 180)
	spark.Parent = point

	local chips = Instance.new("ParticleEmitter")
	chips.Rate = 0
	chips.Lifetime = NumberRange.new(0.3, 0.6)
	chips.Speed = NumberRange.new(8, 16)
	chips.Color = ColorSequence.new(Color3.fromRGB(150, 150, 150))
	chips.Size = NumberSequence.new(0.5)
	chips.SpreadAngle = Vector2.new(180, 180)
	chips.Parent = point

	point.Parent = Workspace
	spark:Emit(isCrit and 22 or 8)
	chips:Emit(isCrit and 10 or 4)
	Debris:AddItem(point, 1)

	-- ④ 타격음 레이어 (3D)
	for _, layer in ipairs(info.hits) do
		SoundBank.play(layer[1], {pitch = layer[2], volume = 0.5, pos = hitPos})
	end

	-- ⑤ 셰이크 (무기 7·8은 더 크게)
	if cameraShake then
		local mag = Config.shake.hit
		if tier >= 7 then
			mag = Config.shake.bigWeapon
		elseif isCrit then
			mag = Config.shake.crit
		end
		cameraShake(mag)
	end

	if isCrit then
		critEdgeFlash()  -- 화면 가장자리 흰 플래시
	end
end

-- ========== 파손 문턱 일회성 연출 (0.66 / 0.33) ==========

local passedThresholds = {}
local roofSmoke = nil

local function checkThresholds(newHp, maxHp, hitPos)
	if maxHp <= 0 then
		return
	end
	local ratio = newHp / maxHp
	if ratio <= 0.66 and not passedThresholds[1] then
		passedThresholds[1] = true
		SoundBank.play("snap", {pitch = 1.3, volume = 0.6})
		task.delay(0.1, function()
			SoundBank.play("snap", {pitch = 1.3, volume = 0.6})
		end)
		if cameraShake then
			cameraShake(Config.shake.crit)
		end
	end
	if ratio <= 0.33 and not passedThresholds[2] then
		passedThresholds[2] = true
		SoundBank.play("snap", {pitch = 1.0, volume = 0.6})
		SoundBank.play("collide", {pitch = 0.9, volume = 0.6})
		-- 파편 크게 한 번
		local point = Instance.new("Part")
		point.Size = Vector3.new(0.2, 0.2, 0.2)
		point.Transparency = 1
		point.Anchored = true
		point.CanCollide = false
		point.CanTouch = false
		point.CanQuery = false
		point.CFrame = CFrame.new(hitPos)
		local chips = Instance.new("ParticleEmitter")
		chips.Rate = 0
		chips.Lifetime = NumberRange.new(0.3, 0.7)
		chips.Speed = NumberRange.new(10, 20)
		chips.Color = ColorSequence.new(Color3.fromRGB(140, 140, 140))
		chips.Size = NumberSequence.new(0.6)
		chips.SpreadAngle = Vector2.new(180, 180)
		chips.Parent = point
		point.Parent = Workspace
		chips:Emit(14)
		Debris:AddItem(point, 1.2)
		-- 옥상 연기 (상시 Rate — 붕괴 때 지붕과 함께 사라짐)
		local building = Workspace:FindFirstChild("건물")
		local roof = building and building:FindFirstChild("지붕")
		if roof and not roofSmoke then
			roofSmoke = Instance.new("ParticleEmitter")
			roofSmoke.Texture = "rbxasset://textures/particles/smoke_main.dds"
			roofSmoke.Rate = 6
			roofSmoke.Lifetime = NumberRange.new(1.2, 2.2)
			roofSmoke.Speed = NumberRange.new(2, 4)
			roofSmoke.Color = ColorSequence.new(Color3.fromRGB(90, 90, 90))
			roofSmoke.Size = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 2),
				NumberSequenceKeypoint.new(1, 5),
			})
			roofSmoke.Transparency = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 0.5),
				NumberSequenceKeypoint.new(1, 1),
			})
			roofSmoke.Parent = roof
		end
	end
end

-- ========== 붕괴 스펙터클 ==========

local function dustColumns()
	local spots = {
		{Vector3.new(0, 1, 0), 70},       -- 바닥 중앙
		{Vector3.new(-10, 1, -5), 20},    -- 네 귀퉁이
		{Vector3.new(10, 1, -5), 20},
		{Vector3.new(-10, 1, 5), 20},
		{Vector3.new(10, 1, 5), 20},
	}
	for _, info in ipairs(spots) do
		local point = Instance.new("Part")
		point.Size = Vector3.new(0.2, 0.2, 0.2)
		point.Transparency = 1
		point.Anchored = true
		point.CanCollide = false
		point.CanTouch = false
		point.CanQuery = false
		point.CFrame = CFrame.new(info[1])
		local smoke = Instance.new("ParticleEmitter")
		smoke.Texture = "rbxasset://textures/particles/smoke_main.dds"
		smoke.Rate = 0
		smoke.Lifetime = NumberRange.new(1.2, 2.5)
		smoke.Speed = NumberRange.new(6, 14)
		smoke.Color = ColorSequence.new(Color3.fromRGB(170, 160, 150))
		smoke.Size = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 3),
			NumberSequenceKeypoint.new(1, 9),
		})
		smoke.Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 0.35),
			NumberSequenceKeypoint.new(1, 1),
		})
		smoke.SpreadAngle = Vector2.new(60, 60)
		smoke.Parent = point
		point.Parent = Workspace
		smoke:Emit(info[2])
		Debris:AddItem(point, 3)
	end
end

function Fx.CollapseFx()
	fullScreenFlash()
	if cameraShake then
		cameraShake(Config.shake.collapse)
	end
	SoundBank.play("splash", {pitch = 0.45, volume = 0.8})
	SoundBank.play("collide", {pitch = 0.4, volume = 0.8})
	dustColumns()
	-- 연기 핸들 리셋 (지붕 파트는 서버 Debris가 치움)
	roofSmoke = nil
	passedThresholds = {}
end

-- ========== 새 건물 층별 등장 ==========

function Fx.RevealBuilding(stage)
	passedThresholds = {}
	roofSmoke = nil
	task.spawn(function()
		-- "지금 스테이지" 건물 모델이 복제될 때까지 대기 (옛 모델과 안 헷갈리게 Stage 속성 확인)
		local building = nil
		for _ = 1, 60 do
			local m = Workspace:FindFirstChild("건물")
			if m and m:GetAttribute("Stage") == stage then
				building = m
				break
			end
			task.wait(0.1)
		end
		if not building then
			return
		end
		-- 블록이 전부 복제될 때까지 잠깐 대기 (층수×4 + 지붕)
		local expected = Config.floorCount(stage) * 4 + 1
		for _ = 1, 40 do
			if #building:GetChildren() >= expected then
				break
			end
			task.wait(0.05)
		end

		-- 블록을 층별로 묶고 일단 전부 숨김 (내 화면만 — LocalTransparencyModifier)
		local byFloor = {}
		local roof = nil
		local topFloor = 0
		for _, b in ipairs(building:GetChildren()) do
			if b:IsA("BasePart") then
				local floorNum = tonumber(string.match(b.Name, "^층(%d+)_"))
				if floorNum then
					byFloor[floorNum] = byFloor[floorNum] or {}
					table.insert(byFloor[floorNum], b)
					topFloor = math.max(topFloor, floorNum)
				elseif b.Name == "지붕" then
					roof = b
				end
				b.LocalTransparencyModifier = 1
			end
		end

		SoundBank.play("getup", {volume = 0.4})
		-- 1층부터 0.08초 간격 공개 (층마다 피치 올라가는 snap)
		for k = 1, topFloor do
			local parts = byFloor[k]
			if parts then
				SoundBank.play("snap", {pitch = 0.8 + 0.05 * k, volume = 0.35})
				for _, b in ipairs(parts) do
					b.LocalTransparencyModifier = 0
				end
			end
			task.wait(0.08)
		end
		if roof then
			roof.LocalTransparencyModifier = 0
			SoundBank.play("snap", {pitch = 1.4, volume = 0.4})
		end
	end)
end

-- ========== HitFx 수신 처리 ==========

function Fx.OnHitFx(attackerUserId, damage, isCrit, hitPos, newHp, maxHp)
	-- 공격자의 무기 tier 알아내기 (Attribute는 자동 복제됨)
	local attacker = Players:GetPlayerByUserId(attackerUserId)
	local tier = attacker and (attacker:GetAttribute("WeaponId") or 1) or 1

	-- 남의 타격이면 그 사람 리그로 스윙 (내 것은 선반영으로 이미 휘두름)
	if attackerUserId ~= player.UserId then
		local rig = rigs[attackerUserId]
		if not rig or rig.tier ~= tier then
			rig = makeRig(attackerUserId, tier)
		end
		playSwing(rig)
	end

	impact(tier, isCrit, hitPos)
	showDamage(damage, isCrit, hitPos)
	checkThresholds(newHp, maxHp, hitPos)
end

function Fx.Init(shakeFn)
	cameraShake = shakeFn
	local playerGui = player:WaitForChild("PlayerGui")
	buildNumberPool(playerGui)
	buildFlash(playerGui)

	-- 내 무기 리그 생성
	makeRig(player.UserId, player:GetAttribute("WeaponId") or 1)

	-- 매 프레임 리그 둥실
	table.insert(connections, RunService.RenderStepped:Connect(updateRigs))

	-- 퇴장한 사람 리그 정리 (누수 방지)
	table.insert(connections, Players.PlayerRemoving:Connect(function(p)
		local rig = rigs[p.UserId]
		if rig and rig.model then
			rig.model:Destroy()
		end
		rigs[p.UserId] = nil
	end))
end

return Fx
