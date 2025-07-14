from flask import Blueprint, render_template, request, redirect, url_for, g, flash
import logging

from app.prompts.manager import PromptManager

logger = logging.getLogger(__name__)
prompts_bp = Blueprint('prompts', __name__, template_folder='../../templates/prompts')

@prompts_bp.route('/')
def list_prompts():
    """Displays a list of all custom prompts."""
    prompts = g.prompt_manager.get_all_prompts()
    return render_template('list_prompts.html', prompts=prompts)

@prompts_bp.route('/create', methods=['GET', 'POST'])
def create_prompt():
    """Handles creation of a new custom prompt."""
    if request.method == 'POST':
        try:
            prompt = g.prompt_manager.create_prompt(
                name=request.form.get('name'),
                description=request.form.get('description'),
                category=request.form.get('category'),
                prompt_template=request.form.get('prompt_template')
            )
            flash(f"Prompt '{prompt.name}' created successfully!", 'success')
            return redirect(url_for('prompts.list_prompts'))
        except ValueError as e:
            flash(str(e), 'danger')
            return render_template('create_prompt.html', form_data=request.form), 400
    
    return render_template('create_prompt.html', form_data={})

@prompts_bp.route('/<prompt_id>/edit', methods=['GET', 'POST'])
def edit_prompt(prompt_id):
    """Handles editing of an existing custom prompt."""
    prompt = g.prompt_manager.get_prompt(prompt_id)
    if not prompt:
        flash(f"Prompt with ID '{prompt_id}' not found.", 'danger')
        return redirect(url_for('prompts.list_prompts'))

    if request.method == 'POST':
        try:
            updates = {
                "name": request.form.get('name'),
                "description": request.form.get('description'),
                "category": request.form.get('category'),
                "prompt_template": request.form.get('prompt_template')
            }
            g.prompt_manager.update_prompt(prompt_id, updates)
            flash(f"Prompt '{updates['name']}' updated successfully!", 'success')
            return redirect(url_for('prompts.list_prompts'))
        except ValueError as e:
            flash(str(e), 'danger')
            # Pass existing prompt data along with form data on error
            form_data = prompt.to_dict()
            form_data.update(request.form)
            return render_template('edit_prompt.html', prompt=prompt, form_data=form_data), 400

    return render_template('edit_prompt.html', prompt=prompt, form_data=prompt.to_dict())

@prompts_bp.route('/<prompt_id>/delete', methods=['POST'])
def delete_prompt(prompt_id):
    """Handles deletion of a custom prompt."""
    prompt = g.prompt_manager.get_prompt(prompt_id)
    if not prompt:
        flash(f"Prompt with ID '{prompt_id}' not found.", 'danger')
    else:
        g.prompt_manager.delete_prompt(prompt_id)
        flash(f"Prompt '{prompt.name}' has been deleted.", 'success')

    return redirect(url_for('prompts.list_prompts')) 