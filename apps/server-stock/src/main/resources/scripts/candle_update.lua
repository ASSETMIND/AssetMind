local key = KEYS[1]
local price = tonumber(ARGV[1])
local volume = tonumber(ARGV[2])

-- 기존 캔들이 존재하지 않으면
if redis.call('EXIST', key) == 0 then
	-- 최초 틱: 시, 고, 저, 종가를 모두 현재 틱으로 초기화
	redis.call('HSET', key, 'open', price, 'high', price, 'low', price, 'close', price, 'volume', volume)
	redis.call('EXPIRE', key, 300) -- 5분뒤 자동 소멸
else
	-- 기존 캔들이 존재하면 갱신
	redis.call('HSET', key, 'close', price)
	redis.call('HINCRBY', key, 'volume', volume)

	local high = tonumber(redis.call('HGET', key, 'high'))
	if price > high then
		redis.call('HSET', key, 'high', price)
	end

	local low = tonumber(redis.call('HGET', key, 'low'))
	if price < low then
		redis.call('HSET', key, 'low', price)
	end
end

return 1