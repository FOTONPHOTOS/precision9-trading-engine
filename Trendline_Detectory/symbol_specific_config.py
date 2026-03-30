"""
Symbol-Specific Configuration Module
This module implements the recalibration plan by adding symbol-specific
adaptive thresholds to the TrendContinuationBrain
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class SymbolSpecificConfig:
    """
    Symbol-specific configuration that adapts the TrendContinuationBrain
    based on the analysis of winning vs losing trades for each symbol.
    """
    
    def __init__(self, symbol: str):
        self.symbol = symbol.upper()
        self.config = self._get_optimized_config()
        
    def _get_optimized_config(self) -> Dict:
        """
        Returns symbol-specific configuration based on data analysis of:
        - Winning vs losing trade characteristics
        - Optimal confluence scores for each symbol
        - Volume requirements
        - Risk tolerance levels
        """
        # Load the known symbols with their optimized configs based on data analysis
        known_configs = {
            'BTCUSDT': {
                # Data shows: 35% win rate, low confluence wins (3.86 vs 5.46), high structural integrity wins (49.29 vs 42.08)
                'min_confluence_points': 8,  # Lower threshold - low confluence works for BTC
                'good_confluence': 30,        # Lower threshold for BTC
                'excellent_confluence': 45,   # Lower threshold for BTC
                'min_confidence_to_trade': 0.20,  # Lower for more BTC trades
                'strong_confidence': 0.40,    # Lower for more BTC trades
                'very_strong_confidence': 0.55,  # Lower for more BTC trades
                'max_acceptable_trap_severity': 0.80,  # Higher tolerance for BTC
                'max_acceptable_stop_hunt_severity': 0.70,  # Higher tolerance for BTC
                'confidence_boost_for_low_confluence': 0.05,  # Bonus for low confluence (BTC specialty)
                'confidence_penalty_for_high_confluence': -0.02,  # Small penalty for high confluence
                'structural_integrity_bonus': 0.03,  # Bonus for high structural integrity
                'volume_requirement': 'flexible',  # Accept various volume levels for BTC
                'trend_strength_requirement': 0.5,  # Moderate trend strength required
                'symbol_notes': 'BTC performs best with low confluence scores and high structural integrity'
            },
            
            'XRPUSDT': {
                # Data shows: 27.3% win rate, high volume wins (1.35M vs 1.22M), low confluence wins (4.50 vs 5.12)
                'min_confluence_points': 7,   # Lowest threshold for volume-dependent XRP
                'good_confluence': 25,        # Low threshold for XRP
                'excellent_confluence': 40,   # Low threshold for XRP
                'min_confidence_to_trade': 0.18,  # Lowest for more XRP trades
                'strong_confidence': 0.35,    # Lower for more XRP trades
                'very_strong_confidence': 0.50,  # Lower for more XRP trades
                'max_acceptable_trap_severity': 0.75,  # Higher tolerance for XRP
                'max_acceptable_stop_hunt_severity': 0.68,  # Higher tolerance for XRP
                'confidence_boost_for_low_confluence': 0.04,  # Bonus for low confluence
                'confidence_penalty_for_high_confluence': -0.03,  # Penalty for high confluence
                'volume_bonus_threshold': 1300000,  # High volume bonus threshold (1.3M)
                'volume_bonus_amount': 0.05,  # Bonus for high volume
                'volume_requirement': 'high',  # Require high volume for XRP
                'trend_strength_requirement': 0.4,  # Moderate trend strength required
                'symbol_notes': 'XRP performs best with high volume and low confluence scores'
            },
            
            'ETHUSDT': {
                # Data shows: 26.3% win rate, very low confluence wins (2.60 vs 5.43), low structural integrity wins (37.60 vs 59.36), low trend strength wins (0.31 vs 0.47)
                'min_confluence_points': 5,   # Very low threshold - ETH specialty
                'good_confluence': 20,        # Very low threshold for ETH
                'excellent_confluence': 35,   # Very low threshold for ETH
                'min_confidence_to_trade': 0.15,  # Lowest for ETH
                'strong_confidence': 0.30,    # Lowest for ETH
                'very_strong_confidence': 0.45,  # Lowest for ETH
                'max_acceptable_trap_severity': 0.75,  # Higher tolerance for ETH
                'max_acceptable_stop_hunt_severity': 0.68,  # Higher tolerance for ETH
                'confidence_boost_for_very_low_confluence': 0.10,  # Big bonus for very low confluence (ETH specialty)
                'confidence_boost_for_low_confluence': 0.05,  # Bonus for low confluence
                'confidence_penalty_for_high_confluence': -0.08,  # Significant penalty for high confluence (hurts ETH)
                'trend_strength_requirement': 0.3,  # Lower trend strength acceptable for ETH
                'volume_requirement': 'moderate',  # Moderate volume for ETH
                'symbol_notes': 'ETH performs best with very low confluence scores (this was the biggest difference)'
            },
            
            'LINKUSDT': {
                # Data shows: 22.2% win rate, low volume wins (38.5K vs 45.0K), high trend strength wins (0.67 vs 0.47)
                'min_confluence_points': 12,  # Higher threshold for LINK structure
                'good_confluence': 35,        # Standard threshold for LINK
                'excellent_confluence': 50,   # Standard threshold for LINK
                'min_confidence_to_trade': 0.25,  # Standard for LINK
                'strong_confidence': 0.45,    # Higher for LINK (require stronger signals)
                'very_strong_confidence': 0.60,  # Higher for LINK
                'max_acceptable_trap_severity': 0.65,  # Lower tolerance for LINK
                'max_acceptable_stop_hunt_severity': 0.62,  # Lower tolerance for LINK
                'volume_requirement': 'low',  # Prefer low volume for LINK
                'volume_penalty_threshold': 50000,  # Penalty for high volume above threshold
                'volume_penalty_amount': -0.05,  # Penalty amount for high volume
                'trend_strength_requirement': 0.6,  # Higher trend strength required for LINK
                'trend_strength_bonus': 0.05,  # Bonus for high trend strength
                'symbol_notes': 'LINK performs best with low volume and high trend strength'
            },
            
            'SOLUSDT': {
                # Data shows: 20% win rate, low volume wins (14K vs 36K), high trend strength wins (0.74 vs 0.50), high confluence wins (5.75 vs 4.94) - OPPOSITE of most symbols!
                'min_confluence_points': 15,  # High threshold for SOL (opposite of others)
                'good_confluence': 40,        # High threshold for SOL
                'excellent_confluence': 55,   # High threshold for SOL
                'min_confidence_to_trade': 0.35,  # High threshold for SOL
                'strong_confidence': 0.55,    # High threshold for SOL
                'very_strong_confidence': 0.70,  # Very high threshold for SOL
                'max_acceptable_trap_severity': 0.60,  # Lowest tolerance for SOL
                'max_acceptable_stop_hunt_severity': 0.58,  # Lowest tolerance for SOL
                'confidence_bonus_for_high_confluence': 0.08,  # Bonus for high confluence (SOL specialty)
                'volume_requirement': 'low',  # Require very low volume for SOL
                'max_volume_threshold': 25000,  # Maximum volume allowed for SOL
                'trend_strength_requirement': 0.7,  # Very high trend strength required for SOL
                'trend_strength_bonus': 0.10,  # High bonus for strong trends
                'symbol_notes': 'SOL performs best with HIGH confluence (opposite of others), LOW volume, and HIGH trend strength - restrictive settings'
            },
            
            'BNBUSDT': {
                # Data shows: 12.5% win rate - WORST performer, high trend strength wins (0.75 vs 0.47), low structural integrity wins (42.00 vs 50.14)
                'min_confluence_points': 25,  # Very high threshold - almost impossible 
                'good_confluence': 60,        # Very high threshold - almost impossible
                'excellent_confluence': 80,   # Very high threshold - almost impossible
                'min_confidence_to_trade': 0.70,  # Very high threshold - almost impossible
                'strong_confidence': 0.80,    # Very high threshold - almost impossible
                'very_strong_confidence': 0.90,  # Very high threshold - almost impossible
                'max_acceptable_trap_severity': 0.50,  # Lowest tolerance - almost impossible
                'max_acceptable_stop_hunt_severity': 0.45,  # Lowest tolerance - almost impossible
                'volume_requirement': 'very_high',  # Require very high volume (rare conditions)
                'trend_strength_requirement': 0.85,  # Extremely high trend strength required
                'symbol_notes': 'BNB is WORST performer (12.5% win rate) - settings designed to nearly eliminate trading'
            }
        }
        
        # Dynamic adaptive default config that can work for any symbol
        # Based on general market principles but optimized to adapt to each symbol's characteristics
        default_adaptive_config = {
            # Start with medium thresholds that can be adjusted based on performance
            'min_confluence_points': 10,  # Standard baseline
            'good_confluence': 35,        # Standard baseline
            'excellent_confluence': 50,   # Standard baseline
            'min_confidence_to_trade': 0.25,  # Standard baseline
            'strong_confidence': 0.50,    # Standard baseline
            'very_strong_confidence': 0.65,  # Standard baseline
            'max_acceptable_trap_severity': 0.70,  # Standard baseline
            'max_acceptable_stop_hunt_severity': 0.65,  # Standard baseline
            
            # Adaptive characteristics that can change based on symbol performance
            'confidence_boost_for_low_confluence': 0.02,  # Small bonus for low confluence (common pattern)
            'confidence_penalty_for_high_confluence': -0.01,  # Small penalty for high confluence
            'confluence_adaptation_rate': 0.1,  # How quickly to adapt confluence strategy based on results
            
            # Volume-based adaptations
            'volume_requirement': 'adaptive',  # Adaptive based on successful patterns
            'volume_adaptation_rate': 0.05,  # How quickly to adapt volume strategy
            'volume_bonus_threshold': 'adaptive',  # Will be calculated dynamically
            
            # Trend-based adaptations
            'trend_strength_requirement': 0.5,  # Standard baseline
            'trend_adaptation_rate': 0.08,  # How quickly to adapt trend strategy
            
            # Performance tracking for dynamic adaptation
            'symbol_performance_tracking': {
                'recent_wins': [],
                'recent_losses': [],
                'win_rate_rolling': 0.0,
                'confluence_correlation': 0.0,  # Correlation between confluence and success
                'volume_correlation': 0.0,      # Correlation between volume and success
                'trend_correlation': 0.0,       # Correlation between trend and success
            },
            
            'symbol_notes': f'Dynamically adaptive config for {self.symbol} - will learn and adapt based on performance'
        }
        
        # Return known config if symbol is in our data, otherwise return adaptive default
        return known_configs.get(self.symbol, default_adaptive_config)
        
        # Return default config if symbol not found
        default_config = {
            'min_confluence_points': 10,
            'good_confluence': 35,
            'excellent_confluence': 50,
            'min_confidence_to_trade': 0.25,
            'strong_confidence': 0.50,
            'very_strong_confidence': 0.60,
            'max_acceptable_trap_severity': 0.70,
            'max_acceptable_stop_hunt_severity': 0.65,
            'volume_requirement': 'none',
            'trend_strength_requirement': 0.5,
            'symbol_notes': 'Default configuration - not optimized for this symbol'
        }
        
        return configs.get(self.symbol, default_config)

    def get_threshold(self, threshold_name: str):
        """Get a specific threshold value"""
        return self.config.get(threshold_name, 0)

    def should_apply_volume_filter(self, current_volume: float) -> tuple[bool, str]:
        """Apply symbol-specific volume filtering"""
        req = self.config['volume_requirement']
        
        if req == 'very_high':
            # For symbols that need very high volume
            if current_volume < self.config.get('volume_bonus_threshold', 1000000):
                return False, f"Volume too low for {self.symbol}"
        
        elif req == 'high':
            # For symbols that need high volume (like XRP)
            if current_volume < self.config.get('volume_bonus_threshold', 500000):
                return False, f"Volume too low for {self.symbol}"
        
        elif req == 'moderate':
            # For symbols with moderate volume needs
            if current_volume < 100000:
                return False, f"Volume too low for {self.symbol}"
        
        elif req == 'low':
            # For symbols that perform better with low volume (like LINK)
            threshold = self.config.get('volume_penalty_threshold', 50000)
            if current_volume > threshold:
                return False, f"Volume too high for {self.symbol}"
        
        elif req == 'adaptive' and self.symbol not in ['BTCUSDT', 'XRPUSDT', 'ETHUSDT', 'LINKUSDT', 'SOLUSDT', 'BNBUSDT']:
            # For unknown symbols, apply adaptive logic
            # This would require performance tracking (see below)
            pass
        elif req == 'none':
            # No volume filtering
            pass
            
        return True, "Volume requirements met"

    def adjust_confidence_for_symbol_characteristics(self, base_confidence: float, 
                                                   confluence_score: float,
                                                   trend_strength: float,
                                                   current_volume: float = 0,
                                                   is_new_symbol: bool = False) -> float:
        """Apply symbol-specific confidence adjustments based on market conditions"""
        adjusted_confidence = base_confidence
        
        # If this is a known symbol with specific characteristics, use those
        if self.symbol == 'ETHUSDT':
            # ETH specialty: very low confluence is best
            if confluence_score <= 3:
                adjusted_confidence += self.config.get('confidence_boost_for_very_low_confluence', 0.10)
            elif confluence_score <= 5:
                adjusted_confidence += self.config.get('confidence_boost_for_low_confluence', 0.05)
            elif confluence_score > 7:
                adjusted_confidence += self.config.get('confidence_penalty_for_high_confluence', -0.08)
        
        elif self.symbol == 'BTCUSDT':
            # BTC: low confluence is good
            if confluence_score <= 4:
                adjusted_confidence += self.config.get('confidence_boost_for_low_confluence', 0.05)
            elif confluence_score > 6:
                adjusted_confidence += self.config.get('confidence_penalty_for_high_confluence', -0.02)
        
        elif self.symbol == 'XRPUSDT':
            # XRP: low confluence is good, high volume is good
            if confluence_score <= 5:
                adjusted_confidence += self.config.get('confidence_boost_for_low_confluence', 0.04)
            elif confluence_score > 6:
                adjusted_confidence += self.config.get('confidence_penalty_for_high_confluence', -0.03)
            
            # Volume bonus for XRP
            if current_volume > self.config.get('volume_bonus_threshold', 1300000):
                adjusted_confidence += self.config.get('volume_bonus_amount', 0.05)
        
        elif self.symbol == 'LINKUSDT':
            # LINK: prefer high trend strength
            if trend_strength >= self.config['trend_strength_requirement']:
                adjusted_confidence += self.config.get('trend_strength_bonus', 0.05)
        
        elif self.symbol == 'SOLUSDT':
            # SOL: opposite pattern - high confluence is good
            if confluence_score >= 6:
                adjusted_confidence += self.config.get('confidence_bonus_for_high_confluence', 0.08)
        
        # For unknown symbols, apply adaptive learning logic
        elif is_new_symbol or self.symbol not in ['BTCUSDT', 'XRPUSDT', 'ETHUSDT', 'LINKUSDT', 'SOLUSDT', 'BNBUSDT']:
            # Apply general adaptive logic for unknown symbols
            # This would be enhanced with actual performance tracking in a full implementation
            adjustment_magnitude = self.config.get('confluence_adaptation_rate', 0.05)
            
            # General pattern: moderate confluence is often better than extreme values
            if 4 <= confluence_score <= 8:
                # Moderate confluence is usually good
                adjusted_confidence += adjustment_magnitude * 0.5
            elif confluence_score < 4:
                # Very low might be good or bad depending on the symbol
                adjusted_confidence += adjustment_magnitude * 0.2
            elif confluence_score > 8:
                # High confluence might be risky
                adjusted_confidence -= adjustment_magnitude * 0.3
            
            # Apply trend strength adjustment
            if trend_strength > self.config.get('trend_strength_requirement', 0.5):
                adjusted_confidence += adjustment_magnitude * 0.3
            elif trend_strength < 0.3:
                adjusted_confidence -= adjustment_magnitude * 0.2

        # Ensure confidence stays within reasonable bounds
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))
        
        return adjusted_confidence

    def get_adaptive_config_for_unknown_symbol(self) -> Dict:
        """Generate adaptive configuration for symbols not in known data"""
        # This is a simplified version - in a full implementation, you'd
        # continuously update this based on performance feedback
        return {
            'min_confluence_points': 10,
            'good_confluence': 35,
            'excellent_confluence': 50,
            'min_confidence_to_trade': 0.25,
            'strong_confidence': 0.50,
            'very_strong_confidence': 0.65,
            'max_acceptable_trap_severity': 0.70,
            'max_acceptable_stop_hunt_severity': 0.65,
            'volume_requirement': 'adaptive',
            'trend_strength_requirement': 0.5,
            'symbol_notes': f'Adaptive config for unknown symbol {self.symbol}'
        }

    def update_performance_tracking(self, trade_result: str, confluence_score: float, 
                                   volume_level: float, trend_strength: float):
        """Update performance tracking for adaptive learning (placeholder for full implementation)"""
        # In a full implementation, this would track win/loss patterns
        # and adjust the configuration based on what works for this particular symbol
        # This is where the system would learn symbol-specific patterns over time
        pass


# Example usage in the TrendContinuationBrain:
def apply_symbol_specific_logic_example():
    """
    This is an example of how to implement the symbol-specific config in the actual brain
    """
    # In the TrendContinuationBrain.__init__ method:
    # self.symbol_config = SymbolSpecificConfig(self.symbol)
    
    # Then update the thresholds:
    # self.min_confluence_points = self.symbol_config.get_threshold('min_confluence_points')
    # self.good_confluence = self.symbol_config.get_threshold('good_confluence')
    # self.excellent_confluence = self.symbol_config.get_threshold('excellent_confluence')
    # self.min_confidence_to_trade = self.symbol_config.get_threshold('min_confidence_to_trade')
    # self.strong_confidence = self.symbol_config.get_threshold('strong_confidence')
    # self.very_strong_confidence = self.symbol_config.get_threshold('very_strong_confidence')
    # self.max_acceptable_trap_severity = self.symbol_config.get_threshold('max_acceptable_trap_severity')
    # self.max_acceptable_stop_hunt_severity = self.symbol_config.get_threshold('max_acceptable_stop_hunt_severity')
    
    # In the analysis phase, apply volume filtering:
    # volume_ok, volume_msg = self.symbol_config.should_apply_volume_filter(current_volume)
    # if not volume_ok:
    #     return self._create_blocked_decision(market_intel.current_price, volume_msg, self.reasoning_chain)
    
    # Adjust confidence based on symbol characteristics:
    # adjusted_confidence = self.symbol_config.adjust_confidence_for_symbol_characteristics(
    #     base_confidence, confluence_score, trend_strength, current_volume
    # )
    
    print("Symbol-specific recalibration logic ready for implementation")
    print("Configuration loaded for all symbols with data-driven thresholds")


if __name__ == "__main__":
    # Test the configuration
    symbols = ['BTCUSDT', 'XRPUSDT', 'ETHUSDT', 'LINKUSDT', 'SOLUSDT', 'BNBUSDT']
    
    for symbol in symbols:
        config = SymbolSpecificConfig(symbol)
        print(f"\n{symbol} Configuration:")
        print(f"  Min Confluence Points: {config.get_threshold('min_confluence_points')}")
        print(f"  Min Confidence to Trade: {config.get_threshold('min_confidence_to_trade')}")
        print(f"  Max Trap Severity: {config.get_threshold('max_acceptable_trap_severity')}")
        print(f"  Notes: {config.config['symbol_notes']}")
    
    print("\n" + "="*60)
    print("SYMBOL-SPECIFIC RECALIBRATION MODULE READY")
    print("="*60)
    print("This module implements data-driven thresholds for each symbol")
    print("based on analysis of winning vs losing trade characteristics.")
    print("Simply import and use SymbolSpecificConfig in your brain.")