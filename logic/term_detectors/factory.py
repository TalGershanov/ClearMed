from logic.term_detectors.base import BaseTermDetector
from logic.term_detectors.english import EnglishTermDetector
from logic.term_detectors.hebrew import HebrewTermDetector


class DetectorFactory:
	_DETECTORS = {
		"en": EnglishTermDetector,
		"he": HebrewTermDetector,
	}

	@classmethod
	def get_detector(cls, language_code: str) -> BaseTermDetector:
		detector_cls = cls._DETECTORS.get(language_code)
		if detector_cls is None:
			raise ValueError(f"Unsupported language_code: {language_code!r}")
		return detector_cls()
