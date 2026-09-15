import math

def calculate_fee(duration_minutes: float) -> float:
    """
    Calculate the parking fee based on the duration in minutes.
    - Grace Period: First 15 minutes = Free (RM 0.00).
    - First Hour: RM 2.00.
    - Subsequent Hours: RM 1.00 per hour (rounded up to the next full hour).
    - Daily Maximum Cap: RM 10.00 per 24 hours.
    """
    if duration_minutes <= 15:
        return 0.0
    
    # Calculate total duration in hours (rounded up)
    duration_hours = math.ceil(duration_minutes / 60)
    if duration_hours == 0:
        duration_hours = 1
    
    # Calculate days and remaining hours
    days = duration_hours // 24
    remaining_hours = duration_hours % 24
    
    # Daily fee is capped at 10.00
    fee = days * 10.0
    
    if remaining_hours > 0:
        remaining_fee = 0.0
        if remaining_hours == 1:
            remaining_fee = 2.0
        else:
            remaining_fee = 2.0 + (remaining_hours - 1) * 1.0
        
        # Apply daily cap to the remaining hours
        if remaining_fee > 10.0:
            remaining_fee = 10.0
            
        fee += remaining_fee
        
    return fee
