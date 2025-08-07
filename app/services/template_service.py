"""Template Management Service for messaging platforms."""
import json
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

import structlog
from pydantic import BaseModel, Field, validator

logger = structlog.get_logger()


class TemplateStatus(str, Enum):
    """Template approval/status enum."""
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISABLED = "disabled"


class TemplateCategory(str, Enum):
    """Template category enum."""
    MARKETING = "marketing"
    UTILITY = "utility"
    AUTHENTICATION = "authentication"
    NOTIFICATION = "notification"


class TemplateComponentType(str, Enum):
    """Template component types."""
    HEADER = "header"
    BODY = "body"
    FOOTER = "footer"
    BUTTONS = "buttons"


class TemplateParameterType(str, Enum):
    """Template parameter types."""
    TEXT = "text"
    CURRENCY = "currency"
    DATE_TIME = "date_time"
    IMAGE = "image"
    DOCUMENT = "document"
    VIDEO = "video"


class TemplateParameter(BaseModel):
    """Template parameter definition."""
    
    name: str = Field(..., description="Parameter name")
    type: TemplateParameterType = Field(TemplateParameterType.TEXT, description="Parameter type")
    required: bool = Field(True, description="Whether parameter is required")
    default_value: str | None = Field(None, description="Default parameter value")
    validation_pattern: str | None = Field(None, description="Regex validation pattern")
    description: str | None = Field(None, description="Parameter description")


class TemplateComponent(BaseModel):
    """Template component (header, body, footer, buttons)."""
    
    type: TemplateComponentType = Field(..., description="Component type")
    text: str | None = Field(None, description="Component text content")
    parameters: List[TemplateParameter] = Field(default_factory=list, description="Component parameters")
    
    # Media-specific fields
    media_url: str | None = Field(None, description="Media URL for header component")
    media_type: str | None = Field(None, description="Media MIME type")
    
    # Button-specific fields
    buttons: List[Dict[str, Any]] = Field(default_factory=list, description="Button definitions")


class PlatformTemplateConfig(BaseModel):
    """Platform-specific template configuration."""
    
    platform: str = Field(..., description="Platform name")
    template_id: str | None = Field(None, description="Platform-specific template ID")
    template_name: str | None = Field(None, description="Platform template name")
    language_code: str = Field("ru", description="Template language")
    
    # Platform-specific settings
    namespace: str | None = Field(None, description="WhatsApp namespace")
    category: TemplateCategory | None = Field(None, description="WhatsApp template category")
    
    # Status tracking
    status: TemplateStatus = Field(TemplateStatus.DRAFT, description="Template status")
    approved_at: datetime | None = Field(None, description="Approval timestamp")
    rejected_reason: str | None = Field(None, description="Rejection reason")


class MessageTemplate(BaseModel):
    """Universal message template."""
    
    # Core template fields
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Template ID")
    name: str = Field(..., description="Template name")
    description: str | None = Field(None, description="Template description")
    
    # Template content
    components: List[TemplateComponent] = Field(default_factory=list, description="Template components")
    language: str = Field("ru", description="Template language")
    category: TemplateCategory = Field(TemplateCategory.UTILITY, description="Template category")
    
    # Platform configurations
    platform_configs: Dict[str, PlatformTemplateConfig] = Field(
        default_factory=dict, description="Platform-specific configurations"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update timestamp")
    created_by: str | None = Field(None, description="Creator user ID")
    
    # Usage tracking
    usage_count: int = Field(0, description="Number of times template was used")
    last_used_at: datetime | None = Field(None, description="Last usage timestamp")
    
    # A/B testing
    variants: List[str] = Field(default_factory=list, description="A/B test variant IDs")
    primary_variant: bool = Field(True, description="Whether this is primary variant")
    
    # Status
    active: bool = Field(True, description="Whether template is active")
    
    @validator('name')
    def validate_name(cls, v):
        """Validate template name format."""
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError("Template name must contain only lowercase letters, numbers, and underscores")
        return v


class TemplateUsageStats(BaseModel):
    """Template usage statistics."""
    
    template_id: str = Field(..., description="Template ID")
    platform: str = Field(..., description="Platform name")
    
    # Usage metrics
    total_sent: int = Field(0, description="Total messages sent")
    successful_deliveries: int = Field(0, description="Successful deliveries")
    failed_deliveries: int = Field(0, description="Failed deliveries")
    
    # Performance metrics
    delivery_rate: float = Field(0.0, description="Delivery success rate")
    open_rate: float = Field(0.0, description="Open rate (if available)")
    click_rate: float = Field(0.0, description="Click rate (if available)")
    
    # Time periods
    date: datetime = Field(default_factory=lambda: datetime.now().date(), description="Stats date")
    last_updated: datetime = Field(default_factory=datetime.now, description="Last update timestamp")


class TemplateRenderContext(BaseModel):
    """Context for template rendering."""
    
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Template parameters")
    user_data: Dict[str, Any] = Field(default_factory=dict, description="User-specific data")
    platform: str = Field(..., description="Target platform")
    language: str = Field("ru", description="Target language")


class RenderedTemplate(BaseModel):
    """Rendered template ready for sending."""
    
    template_id: str = Field(..., description="Source template ID")
    platform: str = Field(..., description="Target platform")
    
    # Rendered content
    text_content: str | None = Field(None, description="Rendered text content")
    components: List[Dict[str, Any]] = Field(default_factory=list, description="Rendered components")
    
    # Platform-specific data
    platform_template_id: str | None = Field(None, description="Platform template ID")
    platform_parameters: List[Dict[str, Any]] = Field(default_factory=list, description="Platform parameters")
    
    # Metadata
    rendered_at: datetime = Field(default_factory=datetime.now, description="Render timestamp")
    render_context: TemplateRenderContext = Field(..., description="Render context")


class TemplateService:
    """Service for managing message templates across platforms."""
    
    def __init__(self):
        """Initialize template service."""
        self.templates: Dict[str, MessageTemplate] = {}
        self.usage_stats: Dict[str, List[TemplateUsageStats]] = {}
        
        logger.info("Template service initialized")
    
    async def create_template(
        self,
        name: str,
        description: str | None = None,
        language: str = "ru",
        category: TemplateCategory = TemplateCategory.UTILITY,
        created_by: str | None = None
    ) -> MessageTemplate:
        """Create a new message template.
        
        Args:
        ----
            name: Template name
            description: Template description
            language: Template language
            category: Template category
            created_by: Creator user ID
            
        Returns:
        -------
            MessageTemplate: Created template
        """
        template = MessageTemplate(
            name=name,
            description=description,
            language=language,
            category=category,
            created_by=created_by
        )
        
        self.templates[template.id] = template
        
        logger.info(
            "Template created",
            template_id=template.id,
            name=name,
            category=category,
            created_by=created_by
        )
        
        return template
    
    async def get_template(self, template_id: str) -> MessageTemplate | None:
        """Get template by ID.
        
        Args:
        ----
            template_id: Template ID
            
        Returns:
        -------
            MessageTemplate | None: Template or None if not found
        """
        return self.templates.get(template_id)
    
    async def list_templates(
        self,
        platform: str | None = None,
        category: TemplateCategory | None = None,
        language: str | None = None,
        active_only: bool = True
    ) -> List[MessageTemplate]:
        """List templates with optional filters.
        
        Args:
        ----
            platform: Filter by platform
            category: Filter by category
            language: Filter by language
            active_only: Only include active templates
            
        Returns:
        -------
            List[MessageTemplate]: Filtered templates
        """
        templates = list(self.templates.values())
        
        if active_only:
            templates = [t for t in templates if t.active]
            
        if platform:
            templates = [t for t in templates if platform in t.platform_configs]
            
        if category:
            templates = [t for t in templates if t.category == category]
            
        if language:
            templates = [t for t in templates if t.language == language]
        
        return sorted(templates, key=lambda x: x.updated_at, reverse=True)
    
    async def update_template(
        self,
        template_id: str,
        **updates
    ) -> MessageTemplate | None:
        """Update template.
        
        Args:
        ----
            template_id: Template ID
            **updates: Fields to update
            
        Returns:
        -------
            MessageTemplate | None: Updated template or None if not found
        """
        template = self.templates.get(template_id)
        if not template:
            return None
        
        # Update fields
        for field, value in updates.items():
            if hasattr(template, field):
                setattr(template, field, value)
        
        template.updated_at = datetime.now()
        
        logger.info(
            "Template updated",
            template_id=template_id,
            updates=list(updates.keys())
        )
        
        return template
    
    async def delete_template(self, template_id: str) -> bool:
        """Delete template.
        
        Args:
        ----
            template_id: Template ID
            
        Returns:
        -------
            bool: Whether template was deleted
        """
        if template_id in self.templates:
            del self.templates[template_id]
            
            # Clean up usage stats
            if template_id in self.usage_stats:
                del self.usage_stats[template_id]
            
            logger.info("Template deleted", template_id=template_id)
            return True
        
        return False
    
    async def add_template_component(
        self,
        template_id: str,
        component: TemplateComponent
    ) -> bool:
        """Add component to template.
        
        Args:
        ----
            template_id: Template ID
            component: Component to add
            
        Returns:
        -------
            bool: Whether component was added
        """
        template = self.templates.get(template_id)
        if not template:
            return False
        
        template.components.append(component)
        template.updated_at = datetime.now()
        
        logger.info(
            "Template component added",
            template_id=template_id,
            component_type=component.type
        )
        
        return True
    
    async def configure_platform(
        self,
        template_id: str,
        platform: str,
        config: PlatformTemplateConfig
    ) -> bool:
        """Configure template for specific platform.
        
        Args:
        ----
            template_id: Template ID
            platform: Platform name
            config: Platform configuration
            
        Returns:
        -------
            bool: Whether configuration was added
        """
        template = self.templates.get(template_id)
        if not template:
            return False
        
        config.platform = platform
        template.platform_configs[platform] = config
        template.updated_at = datetime.now()
        
        logger.info(
            "Template platform configured",
            template_id=template_id,
            platform=platform,
            template_name=config.template_name
        )
        
        return True
    
    async def render_template(
        self,
        template_id: str,
        context: TemplateRenderContext
    ) -> RenderedTemplate | None:
        """Render template with provided context.
        
        Args:
        ----
            template_id: Template ID
            context: Render context
            
        Returns:
        -------
            RenderedTemplate | None: Rendered template or None if template not found
        """
        template = self.templates.get(template_id)
        if not template:
            return None
        
        # Get platform configuration
        platform_config = template.platform_configs.get(context.platform)
        if not platform_config:
            logger.warning(
                "No platform configuration found",
                template_id=template_id,
                platform=context.platform
            )
        
        # Render components
        rendered_components = []
        text_parts = []
        
        for component in template.components:
            rendered_component = await self._render_component(component, context.parameters)
            rendered_components.append(rendered_component)
            
            # Build text content
            if component.type == TemplateComponentType.BODY:
                text_parts.append(rendered_component.get("text", ""))
        
        # Create rendered template
        rendered = RenderedTemplate(
            template_id=template_id,
            platform=context.platform,
            text_content="\n".join(text_parts) if text_parts else None,
            components=rendered_components,
            platform_template_id=platform_config.template_id if platform_config else None,
            platform_parameters=self._build_platform_parameters(
                template, context, platform_config
            ),
            render_context=context
        )
        
        # Update usage tracking
        await self._track_template_usage(template_id, context.platform)
        
        logger.info(
            "Template rendered",
            template_id=template_id,
            platform=context.platform,
            components_count=len(rendered_components)
        )
        
        return rendered
    
    async def _render_component(
        self,
        component: TemplateComponent,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Render individual template component.
        
        Args:
        ----
            component: Component to render
            parameters: Template parameters
            
        Returns:
        -------
            Dict[str, Any]: Rendered component
        """
        rendered = {
            "type": component.type.value
        }
        
        # Render text with parameters
        if component.text:
            rendered_text = component.text
            
            # Replace parameters in text
            for param in component.parameters:
                param_value = parameters.get(param.name, param.default_value or "")
                
                # Validate parameter if pattern provided
                if param.validation_pattern and param_value:
                    if not re.match(param.validation_pattern, str(param_value)):
                        logger.warning(
                            "Parameter validation failed",
                            parameter=param.name,
                            value=param_value,
                            pattern=param.validation_pattern
                        )
                
                # Replace parameter placeholder
                placeholder = f"{{{{{param.name}}}}}"
                rendered_text = rendered_text.replace(placeholder, str(param_value))
            
            rendered["text"] = rendered_text
        
        # Add media information
        if component.media_url:
            rendered["media_url"] = component.media_url
            rendered["media_type"] = component.media_type
        
        # Add buttons
        if component.buttons:
            rendered["buttons"] = component.buttons
        
        return rendered
    
    def _build_platform_parameters(
        self,
        template: MessageTemplate,
        context: TemplateRenderContext,
        platform_config: PlatformTemplateConfig | None
    ) -> List[Dict[str, Any]]:
        """Build platform-specific parameters.
        
        Args:
        ----
            template: Source template
            context: Render context
            platform_config: Platform configuration
            
        Returns:
        -------
            List[Dict[str, Any]]: Platform parameters
        """
        platform_params = []
        
        # Extract all parameters from all components
        all_params = []
        for component in template.components:
            all_params.extend(component.parameters)
        
        # Build platform-specific parameter format
        for param in all_params:
            param_value = context.parameters.get(param.name, param.default_value or "")
            
            if context.platform == "whatsapp":
                # WhatsApp format
                platform_params.append({
                    "type": param.type.value,
                    "text": str(param_value) if param.type == TemplateParameterType.TEXT else param_value
                })
            elif context.platform == "viber":
                # Viber format
                platform_params.append(str(param_value))
            else:
                # Generic format
                platform_params.append({
                    "name": param.name,
                    "value": param_value,
                    "type": param.type.value
                })
        
        return platform_params
    
    async def _track_template_usage(self, template_id: str, platform: str):
        """Track template usage for analytics.
        
        Args:
        ----
            template_id: Template ID
            platform: Platform name
        """
        template = self.templates.get(template_id)
        if template:
            template.usage_count += 1
            template.last_used_at = datetime.now()
        
        # Update usage stats
        today = datetime.now().date()
        stats_key = f"{template_id}_{platform}_{today}"
        
        if template_id not in self.usage_stats:
            self.usage_stats[template_id] = []
        
        # Find or create today's stats
        today_stats = None
        for stats in self.usage_stats[template_id]:
            if stats.platform == platform and stats.date == today:
                today_stats = stats
                break
        
        if not today_stats:
            today_stats = TemplateUsageStats(
                template_id=template_id,
                platform=platform,
                date=today
            )
            self.usage_stats[template_id].append(today_stats)
        
        today_stats.total_sent += 1
        today_stats.last_updated = datetime.now()
    
    async def get_template_stats(
        self,
        template_id: str,
        platform: str | None = None,
        days: int = 30
    ) -> List[TemplateUsageStats]:
        """Get template usage statistics.
        
        Args:
        ----
            template_id: Template ID
            platform: Optional platform filter
            days: Number of days to include
            
        Returns:
        -------
            List[TemplateUsageStats]: Usage statistics
        """
        if template_id not in self.usage_stats:
            return []
        
        cutoff_date = datetime.now().date() - timedelta(days=days)
        stats = self.usage_stats[template_id]
        
        # Filter by date
        filtered_stats = [s for s in stats if s.date >= cutoff_date]
        
        # Filter by platform if specified
        if platform:
            filtered_stats = [s for s in filtered_stats if s.platform == platform]
        
        return sorted(filtered_stats, key=lambda x: x.date, reverse=True)
    
    async def update_delivery_stats(
        self,
        template_id: str,
        platform: str,
        successful: bool,
        date: datetime | None = None
    ):
        """Update template delivery statistics.
        
        Args:
        ----
            template_id: Template ID
            platform: Platform name
            successful: Whether delivery was successful
            date: Stats date (defaults to today)
        """
        if not date:
            date = datetime.now().date()
        
        if template_id not in self.usage_stats:
            self.usage_stats[template_id] = []
        
        # Find stats for the date
        stats = None
        for s in self.usage_stats[template_id]:
            if s.platform == platform and s.date == date:
                stats = s
                break
        
        if not stats:
            return  # No stats to update
        
        # Update delivery counts
        if successful:
            stats.successful_deliveries += 1
        else:
            stats.failed_deliveries += 1
        
        # Recalculate delivery rate
        total_deliveries = stats.successful_deliveries + stats.failed_deliveries
        if total_deliveries > 0:
            stats.delivery_rate = (stats.successful_deliveries / total_deliveries) * 100
        
        stats.last_updated = datetime.now()
    
    async def create_template_variant(
        self,
        base_template_id: str,
        variant_name: str,
        changes: Dict[str, Any]
    ) -> MessageTemplate | None:
        """Create A/B test variant of template.
        
        Args:
        ----
            base_template_id: Base template ID
            variant_name: Variant name
            changes: Changes for variant
            
        Returns:
        -------
            MessageTemplate | None: Variant template or None if base not found
        """
        base_template = self.templates.get(base_template_id)
        if not base_template:
            return None
        
        # Create variant template
        variant = MessageTemplate(**base_template.dict(exclude={"id", "name", "created_at"}))
        variant.name = f"{base_template.name}_{variant_name}"
        variant.primary_variant = False
        
        # Apply changes
        for field, value in changes.items():
            if hasattr(variant, field):
                setattr(variant, field, value)
        
        self.templates[variant.id] = variant
        
        # Link variant to base template
        base_template.variants.append(variant.id)
        
        logger.info(
            "Template variant created",
            base_template_id=base_template_id,
            variant_id=variant.id,
            variant_name=variant_name
        )
        
        return variant
    
    async def get_best_performing_variant(
        self,
        template_id: str,
        platform: str,
        metric: str = "delivery_rate",
        days: int = 7
    ) -> str | None:
        """Get best performing variant of template.
        
        Args:
        ----
            template_id: Base template ID
            platform: Platform name
            metric: Metric to compare (delivery_rate, open_rate, click_rate)
            days: Days to analyze
            
        Returns:
        -------
            str | None: Best variant template ID or None
        """
        template = self.templates.get(template_id)
        if not template or not template.variants:
            return template_id
        
        # Get stats for all variants
        all_variants = [template_id] + template.variants
        best_template_id = template_id
        best_score = 0.0
        
        for variant_id in all_variants:
            stats_list = await self.get_template_stats(variant_id, platform, days)
            if not stats_list:
                continue
            
            # Calculate average metric
            total_score = 0.0
            count = 0
            
            for stats in stats_list:
                if hasattr(stats, metric):
                    total_score += getattr(stats, metric)
                    count += 1
            
            if count > 0:
                avg_score = total_score / count
                if avg_score > best_score:
                    best_score = avg_score
                    best_template_id = variant_id
        
        return best_template_id
    
    async def export_templates(
        self,
        template_ids: List[str] | None = None
    ) -> Dict[str, Any]:
        """Export templates to JSON format.
        
        Args:
        ----
            template_ids: Optional list of template IDs to export
            
        Returns:
        -------
            Dict[str, Any]: Exported templates
        """
        if template_ids:
            templates_to_export = {
                tid: template for tid, template in self.templates.items()
                if tid in template_ids
            }
        else:
            templates_to_export = self.templates
        
        return {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "templates": {
                tid: template.dict() for tid, template in templates_to_export.items()
            }
        }
    
    async def import_templates(
        self,
        export_data: Dict[str, Any],
        overwrite: bool = False
    ) -> List[str]:
        """Import templates from exported JSON.
        
        Args:
        ----
            export_data: Exported template data
            overwrite: Whether to overwrite existing templates
            
        Returns:
        -------
            List[str]: List of imported template IDs
        """
        imported_ids = []
        
        for template_id, template_data in export_data.get("templates", {}).items():
            if template_id in self.templates and not overwrite:
                logger.warning(
                    "Template already exists, skipping",
                    template_id=template_id
                )
                continue
            
            try:
                template = MessageTemplate(**template_data)
                self.templates[template_id] = template
                imported_ids.append(template_id)
                
            except Exception as e:
                logger.error(
                    "Failed to import template",
                    template_id=template_id,
                    error=str(e)
                )
        
        logger.info(
            "Templates imported",
            imported_count=len(imported_ids),
            total_templates=len(export_data.get("templates", {}))
        )
        
        return imported_ids