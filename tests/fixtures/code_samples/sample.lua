-- Sample Lua module for testing code parsing

local M = {}

function M.add(a, b)
    return a + b
end

local function helper(x)
    if x > 0 then
        return x * 2
    else
        return 0
    end
end

function M.process(items)
    local result = 0
    for i, v in ipairs(items) do
        if v > 0 then
            result = result + helper(v)
        end
    end
    return result
end

return M
