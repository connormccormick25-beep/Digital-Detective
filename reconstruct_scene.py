"""
Forensic Architect - Scene Reconstruction Script
Blender script to create a forensic evidence room with breach point marker.
"""

import bpy
import bmesh
from mathutils import Vector
import os
import sys

def clear_scene():
    """Remove all default objects from the scene."""
    # Select all objects
    bpy.ops.object.select_all(action='SELECT')
    
    # Delete all objects
    bpy.ops.object.delete(use_global=False, confirm=False)
    
    # Clear materials
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)
    
    print("Scene cleared.")

def build_room():
    """Create a room with floor and walls."""
    # Room dimensions
    room_size = 20
    wall_height = 8
    wall_thickness = 0.2
    
    # Create floor (large plane)
    bpy.ops.mesh.primitive_plane_add(size=room_size, location=(0, 0, 0))
    floor = bpy.context.active_object
    floor.name = "Floor"
    
    # Create floor material
    floor_material = bpy.data.materials.new(name="FloorMaterial")
    floor_material.use_nodes = True
    floor_material.node_tree.nodes.clear()
    bsdf = floor_material.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.2, 0.2, 0.25, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.8
    output = floor_material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    floor_material.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    floor.data.materials.append(floor_material)
    
    # Create walls (4 scaled cubes)
    wall_positions = [
        (0, -room_size/2, wall_height/2),      # Back wall
        (0, room_size/2, wall_height/2),       # Front wall
        (-room_size/2, 0, wall_height/2),      # Left wall
        (room_size/2, 0, wall_height/2)        # Right wall
    ]
    
    wall_scales = [
        (room_size/2, wall_thickness/2, wall_height/2),   # Back wall
        (room_size/2, wall_thickness/2, wall_height/2),   # Front wall
        (wall_thickness/2, room_size/2, wall_height/2),   # Left wall
        (wall_thickness/2, room_size/2, wall_height/2)    # Right wall
    ]
    
    wall_material = bpy.data.materials.new(name="WallMaterial")
    wall_material.use_nodes = True
    wall_material.node_tree.nodes.clear()
    bsdf = wall_material.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0.85, 0.85, 0.8, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.7
    output = wall_material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    wall_material.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    wall_names = ["BackWall", "FrontWall", "LeftWall", "RightWall"]
    
    for i, (pos, scale, name) in enumerate(zip(wall_positions, wall_scales, wall_names)):
        bpy.ops.mesh.primitive_cube_add(size=2, location=pos)
        wall = bpy.context.active_object
        wall.name = name
        wall.scale = scale
        wall.data.materials.append(wall_material)
    
    print(f"Room built: {room_size}x{room_size} floor, {wall_height} units high.")

def add_evidence_marker():
    """Place a red sphere at the center representing the breach point."""
    # Create sphere at center (0, 0, 1) - slightly above floor
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 1))
    marker = bpy.context.active_object
    marker.name = "BreachPoint"
    
    # Create red material for evidence marker
    marker_material = bpy.data.materials.new(name="BreachMarkerMaterial")
    marker_material.use_nodes = True
    marker_material.node_tree.nodes.clear()
    bsdf = marker_material.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (1.0, 0.0, 0.0, 1.0)  # Bright red
    bsdf.inputs['Roughness'].default_value = 0.3
    bsdf.inputs['Emission'].default_value = (0.5, 0.0, 0.0, 1.0)  # Slight emission
    bsdf.inputs['Emission Strength'].default_value = 0.5
    output = marker_material.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    marker_material.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    marker.data.materials.append(marker_material)
    
    print("Evidence marker (Breach Point) added at room center.")

def setup_lighting_and_camera():
    """Set up sun lamp, point light, and camera pointing at the room."""
    # Add sun lamp
    bpy.ops.object.light_add(type='SUN', location=(10, -10, 15))
    sun = bpy.context.active_object
    sun.name = "ForensicLight"
    sun.data.energy = 5
    sun.rotation_euler = (0.785, 0, 0.785)  # Point towards room center
    
    # Add high-intensity point light at room center (lighting boost)
    bpy.ops.object.light_add(type='POINT', location=(0, 0, 5))
    point_light = bpy.context.active_object
    point_light.name = "CenterPointLight"
    point_light.data.energy = 100  # High intensity for visibility
    point_light.data.shadow_soft_size = 2.0
    
    # Add camera
    bpy.ops.object.camera_add(location=(12, -12, 8))
    camera = bpy.context.active_object
    camera.name = "ForensicCamera"
    
    # Point camera at room center
    camera.rotation_euler = (1.1, 0, 0.785)
    
    # Set camera as active
    bpy.context.scene.camera = camera
    
    print("Lighting and camera set up.")

def render_scene():
    """Set render settings and save image to evidence_renders/latest_render.png
    
    FORCE STABLE HEADLESS RENDERING: Using WORKBENCH engine for highest stability.
    All settings optimized for reliable background rendering without GPU dependencies.
    """
    # Force stable background rendering: Disable splash screen
    try:
        bpy.context.preferences.view.show_splash = False
        print("Splash screen disabled for background rendering", file=sys.stdout)
        sys.stdout.flush()
    except Exception as pref_error:
        print(f"Warning: Could not disable splash screen: {pref_error}", file=sys.stdout)
        sys.stdout.flush()
    
    scene = bpy.context.scene
    
    # FORCE STABLE HEADLESS RENDERING: Use WORKBENCH engine (highest stability)
    scene.render.engine = 'BLENDER_WORKBENCH'
    print("Using BLENDER_WORKBENCH render engine (highest stability for headless rendering)", file=sys.stdout)
    sys.stdout.flush()
    
    # Force CPU rendering: Disable GPU compute devices via cycles preferences
    try:
        if 'cycles' in bpy.context.preferences.addons:
            bpy.context.preferences.addons['cycles'].preferences.compute_device_type = 'NONE'
            print("Forced CPU rendering: cycles compute_device_type set to 'NONE'", file=sys.stdout)
            sys.stdout.flush()
    except Exception as cpu_error:
        print(f"Warning: Could not set cycles compute_device_type: {cpu_error}", file=sys.stdout)
        sys.stdout.flush()
    
    # Ensure viewport render captures shapes without complex lighting
    try:
        scene.display.shading.light = 'FLAT'
        scene.display.shading.color_type = 'OBJECT'
        print("Viewport shading set to FLAT light and OBJECT color type", file=sys.stdout)
        sys.stdout.flush()
    except Exception as shading_error:
        print(f"Warning: Could not set display shading: {shading_error}", file=sys.stdout)
        sys.stdout.flush()
    
    # Set resolution (moderate size for speed)
    scene.render.resolution_x = 800
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    
    # Ensure PNG format is explicitly set
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    
    # Get the directory where THIS script is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, 'evidence_renders')
    
    # Ensure the folder exists for Blender
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}", file=sys.stdout)
        sys.stdout.flush()
    
    output_path = os.path.join(output_dir, 'latest_render.png')
    # Ensure absolute path (Windows compatibility)
    output_path = os.path.abspath(output_path)
    scene.render.filepath = output_path
    
    # Path logging for debugging
    print(f'RENDER_TARGET: {output_path}', file=sys.stdout)
    print(f'RENDER_ENGINE: {scene.render.engine}', file=sys.stdout)
    print(f'RESOLUTION: {scene.render.resolution_x}x{scene.render.resolution_y}', file=sys.stdout)
    sys.stdout.flush()
    
    # Ensure camera is set correctly
    if scene.camera is None:
        print("WARNING: No camera found, trying to find ForensicCamera...", file=sys.stdout)
        sys.stdout.flush()
        if 'ForensicCamera' in bpy.data.objects:
            scene.camera = bpy.data.objects['ForensicCamera']
            print("Camera set to ForensicCamera", file=sys.stdout)
            sys.stdout.flush()
        else:
            print("ERROR: No camera available for rendering!", file=sys.stdout)
            sys.stdout.flush()
            return
    
    # Render the scene
    print("Starting render...", file=sys.stdout)
    sys.stdout.flush()
    try:
        # Force view_layer update before rendering
        view_layer = bpy.context.view_layer
        view_layer.update()
        
        # Perform the render with comprehensive error handling
        # CRITICAL: Wrap in try/except that prints to sys.stdout for Streamlit logs
        try:
            bpy.ops.render.render(write_still=True)
            print("Render operation completed", file=sys.stdout)
            sys.stdout.flush()
        except Exception as render_op_error:
            # Print exact error details to sys.stdout so we can see it in Streamlit logs
            print("=" * 60, file=sys.stdout)
            print("ERROR during render operation (bpy.ops.render.render):", file=sys.stdout)
            print(f"Error Type: {type(render_op_error).__name__}", file=sys.stdout)
            print(f"Error Message: {str(render_op_error)}", file=sys.stdout)
            print("Full Traceback:", file=sys.stdout)
            import traceback
            traceback.print_exc(file=sys.stdout)
            print("=" * 60, file=sys.stdout)
            sys.stdout.flush()
            raise
        
        # Verify file was created
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"Render completed successfully!", file=sys.stdout)
            print(f"Render saved to: {output_path}", file=sys.stdout)
            print(f"File size: {file_size} bytes", file=sys.stdout)
            sys.stdout.flush()
        else:
            print(f"WARNING: Render completed but file not found at: {output_path}", file=sys.stdout)
            print(f"Expected path: {output_path}", file=sys.stdout)
            print(f"Current working directory: {os.getcwd()}", file=sys.stdout)
            sys.stdout.flush()
            
    except Exception as render_error:
        # Catch any other errors during the render process
        print("=" * 60, file=sys.stdout)
        print("ERROR during render process:", file=sys.stdout)
        print(f"Error Type: {type(render_error).__name__}", file=sys.stdout)
        print(f"Error Message: {str(render_error)}", file=sys.stdout)
        print("Full Traceback:", file=sys.stdout)
        import traceback
        traceback.print_exc(file=sys.stdout)
        print("=" * 60, file=sys.stdout)
        sys.stdout.flush()
        raise

def main():
    """Main function to reconstruct the forensic scene. Emergency default - works with or without arguments."""
    print("=" * 50)
    print("Forensic Architect - Scene Reconstruction")
    print("Emergency Default Mode: Building basic evidence room")
    print("=" * 50)
    
    try:
        clear_scene()
        build_room()
        add_evidence_marker()
        setup_lighting_and_camera()
        render_scene()
        
        print("=" * 50)
        print("Scene reconstruction complete!")
        print("=" * 50)
    except Exception as e:
        print(f"ERROR during scene reconstruction: {str(e)}")
        print("Attempting emergency recovery...")
        # Try to render anyway if possible
        try:
            render_scene()
        except:
            print("Emergency recovery failed. Please check Blender installation and script syntax.")

# Execute the reconstruction (Emergency Default - works without arguments)
if __name__ == "__main__":
    main()


