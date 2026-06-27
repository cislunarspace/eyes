use base64::{engine::general_purpose, Engine};
use png::{BitDepth, ColorType, Encoder};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Frame {
    pub width: u32,
    pub height: u32,
    pub rgb: Vec<u8>,
}

impl Frame {
    pub fn rgb(width: u32, height: u32, rgb: Vec<u8>) -> Result<Self, FrameError> {
        if width == 0 || height == 0 {
            return Err(FrameError::InvalidDimensions { width, height });
        }
        let expected_len = (width as usize)
            .checked_mul(height as usize)
            .and_then(|pixels| pixels.checked_mul(3))
            .ok_or(FrameError::DimensionOverflow { width, height })?;
        if rgb.len() != expected_len {
            return Err(FrameError::InvalidRgbLength {
                expected: expected_len,
                actual: rgb.len(),
            });
        }
        Ok(Self { width, height, rgb })
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FrameError {
    InvalidDimensions { width: u32, height: u32 },
    DimensionOverflow { width: u32, height: u32 },
    InvalidRgbLength { expected: usize, actual: usize },
    EncodeFailed,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PreviewFrame {
    pub image_data_url: String,
    pub width: u32,
    pub height: u32,
}

pub fn encode_preview(frame: &Frame) -> Result<PreviewFrame, FrameError> {
    let mut png_bytes = Vec::new();
    {
        let mut encoder = Encoder::new(&mut png_bytes, frame.width, frame.height);
        encoder.set_color(ColorType::Rgb);
        encoder.set_depth(BitDepth::Eight);
        let mut writer = encoder
            .write_header()
            .map_err(|_| FrameError::EncodeFailed)?;
        writer
            .write_image_data(&frame.rgb)
            .map_err(|_| FrameError::EncodeFailed)?;
    }

    Ok(PreviewFrame {
        image_data_url: format!(
            "data:image/png;base64,{}",
            general_purpose::STANDARD.encode(png_bytes)
        ),
        width: frame.width,
        height: frame.height,
    })
}
