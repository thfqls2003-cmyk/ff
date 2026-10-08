-- 입력 (클라)
-- 화면 전체를 덮는 투명 버튼이라 어디를 눌러도 공격! (모바일 탭 + PC 클릭 + 스페이스)
-- 0.125초보다 빠른 연타는 아예 무시해서 스윙 1번 = 신호 1번을 지켜요.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

local GameFolder = ReplicatedStorage:WaitForChild("Game")
local Config = require(GameFolder:WaitForChild("Config"))

local Input = {}

local connections = {}
local lastFire = 0

function Input.Init(remotes, onSwing)
	local player = Players.LocalPlayer
	local playerGui = player:WaitForChild("PlayerGui")

	-- 공격 1회 시도 (쓰로틀 통과 시에만 스윙+발신)
	local function attack()
		local now = os.clock()
		if now - lastFire < Config.clientClickGap then
			return  -- 너무 빠른 연타는 통째로 무시
		end
		lastFire = now
		if onSwing then
			onSwing()  -- 스윙 선반영 (서버 응답을 기다리지 않고 즉시 휘두름)
		end
		remotes.Hit:FireServer()
	end

	-- 화면 전체 투명 버튼
	local gui = Instance.new("ScreenGui")
	gui.Name = "탭잡이"
	gui.ResetOnSpawn = false
	gui.IgnoreGuiInset = true
	gui.DisplayOrder = 1  -- HUD(10)보다 아래 → 구매 버튼이 먼저 눌려요

	local button = Instance.new("TextButton")
	button.Name = "전체화면버튼"
	button.Size = UDim2.fromScale(1, 1)
	button.Position = UDim2.fromScale(0, 0)
	button.BackgroundTransparency = 1
	button.Text = ""
	button.AutoButtonColor = false
	button.Parent = gui

	gui.Parent = playerGui

	table.insert(connections, button.Activated:Connect(attack))

	-- 스페이스 키 보조 (gameProcessed면 무시 — 채팅 입력 중에는 안 때리게)
	table.insert(connections, UserInputService.InputBegan:Connect(function(input, gameProcessed)
		if gameProcessed then
			return
		end
		if input.KeyCode == Enum.KeyCode.Space then
			attack()
		end
	end))
end

return Input
