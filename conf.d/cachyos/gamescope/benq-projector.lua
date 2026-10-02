-- BenQ projector on HDMI-A-1: treat as SDR-only.
-- Its EDID advertises HDR/BT.2020, so gamescope sends HDR infoframes, but the
-- RTX 2080 Ti can't do HDR at 4K60 over HDMI (600 MHz TMDS limit) and every
-- atomic commit fails with EINVAL, leaving the screen frozen/black.

-- The EDID white point (0.2832, 0.3945) is bogus (D65 is 0.3127, 0.3290), and
-- gamescope's colour management "corrects" for it, tinting everything orange.
-- Claim plain Rec.709/sRGB with D65 so gamescope sends colours unchanged.
local rec709_colorimetry = {
    r = { x = 0.6400, y = 0.3300 },
    g = { x = 0.3000, y = 0.6000 },
    b = { x = 0.1500, y = 0.0600 },
    w = { x = 0.3127, y = 0.3290 }
}

gamescope.config.known_displays.benq_projector = {
    pretty_name = "BenQ Projector",
    colorimetry = rec709_colorimetry,
    hdr = {
        supported = false,
        force_enabled = false,
        eotf = gamescope.eotf.gamma22,
        max_content_light_level = 400,
        max_frame_average_luminance = 400,
        min_content_light_level = 0.5
    },
    matches = function(display)
        -- gamescope logs this display as "BNQ - BenQ PJ"
        if display.vendor == "BNQ" and display.model == "BenQ PJ" then
            debug("[benq_projector] Matched vendor: BNQ model: BenQ PJ")
            return 5000
        end
        return -1
    end
}
debug("Registered BenQ Projector as a known display")
