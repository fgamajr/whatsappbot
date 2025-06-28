from pydantic import BaseModel, field_validator, validator
import re


class BrazilianPhoneNumber(BaseModel):
    number: str
    
    @field_validator('number')
    @classmethod
    def validate_brazilian_number(cls, v):
        # Remove any non-digits
        clean_number = re.sub(r'\D', '', v)
        
        # Brazilian mobile pattern: 55 + area code (2 digits) + mobile number
        if not clean_number.startswith('55'):
            raise ValueError('Number must start with country code 55')
        
        # Check length (should be 13 digits for mobile)
        if len(clean_number) not in [12, 13]:
            raise ValueError('Invalid Brazilian mobile number length')
        
        # Fix missing 9th digit if needed
        if len(clean_number) == 12:
            area_code = clean_number[2:4]
            valid_area_codes = [
                "11", "12", "13", "14", "15", "16", "17", "18", "19",
                "21", "22", "24", "27", "28", "31", "32", "33", "34",
                "35", "37", "38", "41", "42", "43", "44", "45", "46",
                "47", "48", "49", "51", "53", "54", "55", "61", "62",
                "63", "64", "65", "66", "67", "68", "69", "71", "73",
                "74", "75", "77", "79", "81", "82", "83", "84", "85",
                "86", "87", "88", "89", "91", "92", "93", "94", "95",
                "96", "97", "98", "99"
            ]
            
            if area_code in valid_area_codes:
                # Insert 9 after area code
                clean_number = clean_number[:4] + "9" + clean_number[4:]
        
        return clean_number
    
    def __str__(self):
        return self.number
